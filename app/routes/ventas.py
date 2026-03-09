from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta
from app.models import (User, Cliente, Venta, DetalleVenta, Pago, 
                       CategoriaHuevo, Huevo, LoteRecoleccion, 
                       InventarioHuevos, ConfiguracionVenta)
from app import db
from app.utils.excel import create_excel_response, create_excel_multisheet_response
import uuid

ventas_bp = Blueprint('ventas', __name__, url_prefix='/ventas')


def _redirect_back(default_endpoint='ventas.historial_ventas', **values):
    destino = request.form.get('next') or request.args.get('next') or request.referrer
    if destino:
        return redirect(destino)
    return redirect(url_for(default_endpoint, **values))


@ventas_bp.route('/')
@login_required
def ventas_dashboard():
    """Panel principal de ventas"""
    # Estadísticas de ventas del día
    hoy = datetime.now().date()
    
    ventas_hoy = Venta.query.filter(
        func.date(Venta.fecha_venta) == hoy
    ).count()
    
    ingresos_hoy = db.session.query(func.sum(Venta.total)).filter(
        func.date(Venta.fecha_venta) == hoy,
        Venta.estado.in_(['completada', 'parcial', 'pendiente'])
    ).scalar() or 0
    
    # Inventario disponible por categoría
    inventario_disponible = db.session.query(
        CategoriaHuevo.nombre,
        CategoriaHuevo.id,
        CategoriaHuevo.precio_venta,
        func.count(Huevo.id).label('cantidad')
    ).join(
        Huevo, CategoriaHuevo.id == Huevo.categoria_id
    ).filter(
        Huevo.roto == False,
        Huevo.vendido == False,
        CategoriaHuevo.activo == True
    ).group_by(
        CategoriaHuevo.id, CategoriaHuevo.nombre, CategoriaHuevo.precio_venta
    ).all()
    
    # Clientes con saldo pendiente
    clientes_pendientes = Cliente.query.join(Venta).filter(
        Venta.estado.in_(['pendiente', 'parcial']),
        Cliente.activo == True
    ).distinct().limit(10).all()
    
    return render_template('ventas/dashboard.html',
                         title='Dashboard Ventas',
                         ventas_hoy=ventas_hoy,
                         ingresos_hoy=ingresos_hoy,
                         inventario_disponible=inventario_disponible,
                         clientes_pendientes=clientes_pendientes)


@ventas_bp.route('/nueva')
@login_required
def nueva_venta():
    """Formulario para nueva venta"""
    # Obtener inventario disponible
    inventario = db.session.query(
        CategoriaHuevo.id,
        CategoriaHuevo.nombre,
        CategoriaHuevo.precio_venta,
        CategoriaHuevo.peso_min,
        CategoriaHuevo.peso_max,
        func.count(Huevo.id).label('cantidad_disponible')
    ).join(
        Huevo, CategoriaHuevo.id == Huevo.categoria_id
    ).filter(
        Huevo.roto == False,
        Huevo.vendido == False,
        CategoriaHuevo.activo == True
    ).group_by(
        CategoriaHuevo.id, CategoriaHuevo.nombre, 
        CategoriaHuevo.precio_venta, CategoriaHuevo.peso_min, CategoriaHuevo.peso_max
    ).all()
    
    # Clientes activos para venta a crédito
    clientes = Cliente.query.filter_by(activo=True).order_by(Cliente.nombre).all()
    
    return render_template('ventas/nueva_venta.html',
                         title='Nueva Venta',
                         inventario=inventario,
                         clientes=clientes)


@ventas_bp.route('/procesar', methods=['POST'])
@login_required
def procesar_venta():
    """Procesar una nueva venta"""
    try:
        data = request.get_json()
        
        # Validar datos
        if not data or not data.get('detalles') or len(data['detalles']) == 0:
            return jsonify({'error': 'No hay productos en la venta'}), 400
        
        tipo_pago = data.get('tipo_pago', 'contado')
        cliente_id = data.get('cliente_id') if tipo_pago == 'credito' else None
        descuento = float(data.get('descuento', 0))
        
        # Validar cliente si es venta a credito
        cliente = None
        if tipo_pago == 'credito':
            if not cliente_id:
                return jsonify({'error': 'Cliente requerido para venta a credito'}), 400
            cliente = Cliente.query.get(cliente_id)
            if not cliente or not cliente.activo:
                return jsonify({'error': 'Cliente no valido'}), 400
        else:
            # Para contado, asegurar un cliente generico si la BD no permite NULL
            if not cliente_id:
                cliente = Cliente.query.filter_by(numero_identificacion='CONTADO').first()
                if not cliente:
                    cliente = Cliente(
                        nombre='Cliente',
                        apellido='Contado',
                        tipo_identificacion='NA',
                        numero_identificacion='CONTADO',
                        limite_credito=0,
                        activo=True
                    )
                    db.session.add(cliente)
                    db.session.flush()
                cliente_id = cliente.id

        # Calcular subtotal y verificar inventario
        subtotal = 0
        detalles_procesados = []
        
        for detalle in data['detalles']:
            categoria_id = detalle['categoria_id']
            cantidad_huevos = int(detalle['cantidad_huevos'])
            precio_unitario = float(detalle['precio_unitario'])
            
            # Verificar inventario disponible
            disponibles = db.session.query(func.count(Huevo.id)).filter(
                Huevo.categoria_id == categoria_id,
                Huevo.roto == False,
                Huevo.vendido == False
            ).scalar()
            
            if disponibles < cantidad_huevos:
                categoria = CategoriaHuevo.query.get(categoria_id)
                return jsonify({
                    'error': f'No hay suficientes huevos disponibles de categoría {categoria.nombre}. Disponibles: {disponibles}'
                }), 400
            
            subtotal_item = cantidad_huevos * precio_unitario
            subtotal += subtotal_item
            
            detalles_procesados.append({
                'categoria_id': categoria_id,
                'cantidad_huevos': cantidad_huevos,
                'cantidad_paneles': cantidad_huevos // 30,
                'precio_unitario': precio_unitario,
                'subtotal': subtotal_item
            })
        
        total = subtotal - descuento
        
        # Verificar límite de crédito si aplica
        if tipo_pago == 'credito' and not cliente.puede_comprar_a_credito(total):
            return jsonify({
                'error': f'Límite de crédito excedido. Saldo actual: ${cliente.get_saldo_pendiente():.2f}, Límite: ${cliente.limite_credito:.2f}'
            }), 400
        
        # Generar número de venta
        numero_venta = f"VTA-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        
        # Crear la venta
        venta = Venta(
            numero_venta=numero_venta,
            cliente_id=cliente_id,
            vendedor_id=current_user.id,
            tipo_pago=tipo_pago,
            estado='completada' if tipo_pago == 'contado' else 'pendiente',
            subtotal=subtotal,
            descuento=descuento,
            total=total,
            observaciones=data.get('observaciones', '')
        )
        
        if tipo_pago == 'credito':
            # Calcular fecha de vencimiento (30 días por defecto)
            venta.fecha_vencimiento = datetime.now() + timedelta(days=30)
        
        db.session.add(venta)
        db.session.flush()  # Para obtener el ID de la venta
        
        # Crear detalles y marcar huevos como vendidos
        for detalle_data in detalles_procesados:
            detalle = DetalleVenta(
                venta_id=venta.id,
                categoria_id=detalle_data['categoria_id'],
                cantidad_huevos=detalle_data['cantidad_huevos'],
                cantidad_paneles=detalle_data['cantidad_paneles'],
                precio_unitario=detalle_data['precio_unitario'],
                subtotal=detalle_data['subtotal']
            )
            db.session.add(detalle)
            
            # Marcar huevos como vendidos (FIFO - First In, First Out)
            huevos_a_vender = db.session.query(Huevo).join(LoteRecoleccion).filter(
                Huevo.categoria_id == detalle_data['categoria_id'],
                Huevo.roto == False,
                Huevo.vendido == False
            ).order_by(LoteRecoleccion.fecha_recoleccion).limit(detalle_data['cantidad_huevos']).all()
            
            for huevo in huevos_a_vender:
                huevo.vendido = True
                huevo.fecha_venta = datetime.now()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'venta_id': venta.id,
            'numero_venta': venta.numero_venta,
            'total': float(venta.total),
            'mensaje': 'Venta procesada exitosamente'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error procesando la venta: {str(e)}'}), 500


@ventas_bp.route('/historial')
@login_required
def historial_ventas():
    """Historial de ventas"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Filtros
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    tipo_pago = request.args.get('tipo_pago')
    estado = request.args.get('estado')
    cliente_id = request.args.get('cliente_id')
    
    query = Venta.query
    
    # Aplicar filtros
    if fecha_inicio:
        query = query.filter(Venta.fecha_venta >= datetime.strptime(fecha_inicio, '%Y-%m-%d'))
    if fecha_fin:
        query = query.filter(Venta.fecha_venta <= datetime.strptime(fecha_fin + ' 23:59:59', '%Y-%m-%d %H:%M:%S'))
    if tipo_pago:
        query = query.filter(Venta.tipo_pago == tipo_pago)
    if estado:
        query = query.filter(Venta.estado == estado)
    if cliente_id:
        query = query.filter(Venta.cliente_id == cliente_id)
    
    # Totales globales segun filtros aplicados (no solo la pagina actual)
    pagos_subq = db.session.query(
        Pago.venta_id.label('venta_id'),
        func.coalesce(func.sum(Pago.monto), 0).label('monto_pagado')
    ).group_by(Pago.venta_id).subquery()

    totales_row = query.outerjoin(
        pagos_subq, pagos_subq.c.venta_id == Venta.id
    ).with_entities(
        func.coalesce(func.sum(Venta.total), 0).label('total_ventas'),
        func.coalesce(func.sum(func.coalesce(pagos_subq.c.monto_pagado, 0)), 0).label('total_pagado'),
        func.coalesce(
            func.sum(Venta.total - func.coalesce(pagos_subq.c.monto_pagado, 0)),
            0
        ).label('total_debe')
    ).first()

    ventas = query.order_by(Venta.fecha_venta.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # Monto pagado/saldo por cada venta visible en la pagina actual
    venta_ids = [v.id for v in ventas.items]
    pagos_por_venta = {}
    if venta_ids:
        pagos_rows = db.session.query(
            Pago.venta_id,
            func.coalesce(func.sum(Pago.monto), 0).label('monto_pagado')
        ).filter(
            Pago.venta_id.in_(venta_ids)
        ).group_by(Pago.venta_id).all()
        pagos_por_venta = {venta_id: float(monto_pagado or 0) for venta_id, monto_pagado in pagos_rows}
    
    # Obtener clientes para el filtro
    clientes = Cliente.query.filter_by(activo=True).order_by(Cliente.nombre).all()
    
    return render_template('ventas/historial.html',
                         title='Historial de Ventas',
                         ventas=ventas,
                         clientes=clientes,
                         pagos_por_venta=pagos_por_venta,
                         totales_historial={
                             'total_ventas': float(totales_row.total_ventas or 0),
                             'total_pagado': float(totales_row.total_pagado or 0),
                             'total_debe': max(0, float(totales_row.total_debe or 0))
                         })


@ventas_bp.route('/detalle/<int:venta_id>')
@login_required
def detalle_venta(venta_id):
    """Ver detalle de una venta específica"""
    venta = Venta.query.get_or_404(venta_id)
    
    return render_template('ventas/detalle_venta.html',
                         title=f'Venta {venta.numero_venta}',
                         venta=venta)


@ventas_bp.route('/export/excel')
@login_required
def export_excel_ventas():
    """Exportar tablas del modulo ventas a Excel"""
    tabla = request.args.get('tabla', '').strip()

    if tabla == 'historial':
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        tipo_pago = request.args.get('tipo_pago')
        estado = request.args.get('estado')
        cliente_id = request.args.get('cliente_id')

        query = Venta.query
        if fecha_inicio:
            query = query.filter(Venta.fecha_venta >= datetime.strptime(fecha_inicio, '%Y-%m-%d'))
        if fecha_fin:
            query = query.filter(Venta.fecha_venta <= datetime.strptime(fecha_fin + ' 23:59:59', '%Y-%m-%d %H:%M:%S'))
        if tipo_pago:
            query = query.filter(Venta.tipo_pago == tipo_pago)
        if estado:
            query = query.filter(Venta.estado == estado)
        if cliente_id:
            query = query.filter(Venta.cliente_id == cliente_id)

        ventas = query.order_by(Venta.fecha_venta.desc()).all()
        rows = [[
            v.numero_venta,
            v.fecha_venta,
            v.cliente.get_nombre_completo() if v.cliente else 'N/A',
            v.tipo_pago,
            float(v.subtotal or 0),
            float(v.descuento or 0),
            float(v.total or 0),
            float(v.get_monto_pagado() or 0),
            float(v.get_saldo_pendiente() or 0),
            v.estado
        ] for v in ventas]
        return create_excel_response(
            'ventas_historial.xlsx',
            'Historial',
            ['Numero Venta', 'Fecha', 'Cliente', 'Tipo Pago', 'Subtotal', 'Descuento', 'Total', 'Pagado', 'Saldo', 'Estado'],
            rows
        )

    if tabla == 'clientes':
        search = request.args.get('search', '').strip()
        query = Cliente.query
        if search:
            query = query.filter(
                or_(
                    Cliente.nombre.contains(search),
                    Cliente.apellido.contains(search),
                    Cliente.numero_identificacion.contains(search),
                    Cliente.telefono.contains(search)
                )
            )
        clientes = query.order_by(Cliente.nombre).all()
        rows = [[
            c.get_nombre_completo(),
            c.telefono or '',
            c.numero_identificacion or '',
            float(c.limite_credito or 0),
            float(c.get_saldo_pendiente() or 0),
            float(c.get_credito_disponible() or 0),
            'Activo' if c.activo else 'Inactivo'
        ] for c in clientes]
        return create_excel_response(
            'ventas_clientes.xlsx',
            'Clientes',
            ['Cliente', 'Telefono', 'Identificacion', 'Limite Credito', 'Saldo Pendiente', 'Credito Disponible', 'Estado'],
            rows
        )

    if tabla == 'cartera_cliente':
        cliente_id = request.args.get('cliente_id', type=int)
        cliente = Cliente.query.get_or_404(cliente_id)
        ventas_pendientes = Venta.query.filter(
            Venta.cliente_id == cliente_id,
            Venta.estado.in_(['pendiente', 'parcial'])
        ).order_by(Venta.fecha_venta.desc()).all()
        rows_ventas = [[
            v.numero_venta,
            v.fecha_venta,
            float(v.total or 0),
            float(v.get_monto_pagado() or 0),
            float(v.get_saldo_pendiente() or 0),
            v.estado
        ] for v in ventas_pendientes]
        pagos = Pago.query.filter_by(cliente_id=cliente_id).order_by(Pago.fecha_pago.desc()).all()
        rows_pagos = [[
            p.numero_pago,
            p.fecha_pago,
            p.venta.numero_venta if p.venta else '',
            float(p.monto or 0),
            p.forma_pago,
            p.receptor.get_full_name() if p.receptor else ''
        ] for p in pagos]
        return create_excel_multisheet_response(
            f'cartera_{cliente.nombre}_{cliente.apellido}.xlsx',
            [
                {
                    'name': 'Ventas Pendientes',
                    'headers': ['Numero Venta', 'Fecha', 'Total', 'Pagado', 'Saldo', 'Estado'],
                    'rows': rows_ventas
                },
                {
                    'name': 'Pagos',
                    'headers': ['Numero Pago', 'Fecha', 'Venta', 'Monto', 'Forma Pago', 'Recibido Por'],
                    'rows': rows_pagos
                }
            ]
        )

    if tabla == 'detalle_venta':
        venta_id = request.args.get('venta_id', type=int)
        venta = Venta.query.get_or_404(venta_id)
        detalles = venta.detalles.all()
        rows = [[
            d.categoria.nombre if d.categoria else 'N/A',
            d.cantidad_huevos,
            d.cantidad_paneles,
            float(d.precio_unitario or 0),
            float(d.subtotal or 0)
        ] for d in detalles]
        return create_excel_response(
            f'detalle_{venta.numero_venta}.xlsx',
            'Detalle Venta',
            ['Categoria', 'Huevos', 'Paneles', 'Precio Unitario', 'Subtotal'],
            rows
        )

    if tabla == 'dashboard_inventario':
        inventario_disponible = db.session.query(
            CategoriaHuevo.nombre,
            CategoriaHuevo.id,
            CategoriaHuevo.precio_venta,
            func.count(Huevo.id).label('cantidad')
        ).join(
            Huevo, CategoriaHuevo.id == Huevo.categoria_id
        ).filter(
            Huevo.roto == False,
            Huevo.vendido == False,
            CategoriaHuevo.activo == True
        ).group_by(
            CategoriaHuevo.id, CategoriaHuevo.nombre, CategoriaHuevo.precio_venta
        ).all()
        rows = [[
            i.nombre,
            i.cantidad,
            i.cantidad // 30,
            i.cantidad % 30,
            float(i.precio_venta or 0)
        ] for i in inventario_disponible]
        return create_excel_response(
            'ventas_dashboard_inventario.xlsx',
            'Inventario',
            ['Categoria', 'Cantidad', 'Paneles', 'Huevos Sueltos', 'Precio'],
            rows
        )

    if tabla == 'dashboard_cartera':
        clientes_pendientes = Cliente.query.join(Venta).filter(
            Venta.estado.in_(['pendiente', 'parcial']),
            Cliente.activo == True
        ).distinct().all()
        rows = [[
            c.get_nombre_completo(),
            c.numero_identificacion or '',
            float(c.get_saldo_pendiente() or 0)
        ] for c in clientes_pendientes]
        return create_excel_response(
            'ventas_dashboard_cartera.xlsx',
            'Cartera',
            ['Cliente', 'Identificacion', 'Saldo Pendiente'],
            rows
        )

    flash('Tipo de tabla no valido para exportar', 'danger')
    return redirect(url_for('ventas.ventas_dashboard'))


@ventas_bp.route('/clientes')
@login_required
def lista_clientes():
    """Lista de clientes"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    search = request.args.get('search', '')
    
    query = Cliente.query
    
    if search:
        query = query.filter(
            or_(
                Cliente.nombre.contains(search),
                Cliente.apellido.contains(search),
                Cliente.numero_identificacion.contains(search),
                Cliente.telefono.contains(search)
            )
        )
    
    clientes = query.order_by(Cliente.nombre).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('ventas/clientes.html',
                         title='Clientes',
                         clientes=clientes,
                         search=search)


@ventas_bp.route('/clientes/nuevo')
@login_required
def nuevo_cliente():
    """Formulario para nuevo cliente"""
    return render_template('ventas/nuevo_cliente.html',
                         title='Nuevo Cliente')


@ventas_bp.route('/clientes/crear', methods=['POST'])
@login_required
def crear_cliente():
    """Crear un nuevo cliente"""
    try:
        nombre = request.form.get('nombre', '').strip()
        apellido = request.form.get('apellido', '').strip()
        telefono = request.form.get('telefono', '').strip()
        email = request.form.get('email', '').strip()
        direccion = request.form.get('direccion', '').strip()
        tipo_identificacion = request.form.get('tipo_identificacion')
        numero_identificacion = request.form.get('numero_identificacion', '').strip()
        limite_credito = float(request.form.get('limite_credito', 0))
        
        # Validaciones
        if not nombre or not apellido:
            flash('Nombre y apellido son obligatorios', 'danger')
            return redirect(url_for('ventas.nuevo_cliente'))
        
        if numero_identificacion:
            cliente_existente = Cliente.query.filter_by(
                numero_identificacion=numero_identificacion
            ).first()
            if cliente_existente:
                flash('Ya existe un cliente con ese número de identificación', 'danger')
                return redirect(url_for('ventas.nuevo_cliente'))
        
        # Crear cliente
        cliente = Cliente(
            nombre=nombre,
            apellido=apellido,
            telefono=telefono or None,
            email=email or None,
            direccion=direccion or None,
            tipo_identificacion=tipo_identificacion,
            numero_identificacion=numero_identificacion or None,
            limite_credito=limite_credito
        )
        
        db.session.add(cliente)
        db.session.commit()
        
        flash(f'Cliente {cliente.get_nombre_completo()} creado exitosamente', 'success')
        return redirect(url_for('ventas.lista_clientes'))
        
    except ValueError:
        flash('Error en los datos proporcionados', 'danger')
        return redirect(url_for('ventas.nuevo_cliente'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error creando cliente: {str(e)}', 'danger')
        return redirect(url_for('ventas.nuevo_cliente'))


@ventas_bp.route('/api/clientes/crear', methods=['POST'])
@login_required
def api_crear_cliente():
    """Crear cliente via AJAX para el modal de nueva venta."""
    try:
        nombre = (request.form.get('nombre') or '').strip()
        apellido = (request.form.get('apellido') or '').strip()
        telefono = (request.form.get('telefono') or '').strip()
        tipo_identificacion = (request.form.get('tipo_identificacion') or '').strip() or None
        numero_identificacion = (request.form.get('numero_identificacion') or '').strip()
        limite_credito = float(request.form.get('limite_credito') or 0)

        if not nombre or not apellido:
            return jsonify({'success': False, 'error': 'Nombre y apellido son obligatorios'}), 400

        if limite_credito < 0:
            return jsonify({'success': False, 'error': 'El límite de crédito no puede ser negativo'}), 400

        if numero_identificacion:
            cliente_existente = Cliente.query.filter_by(
                numero_identificacion=numero_identificacion
            ).first()
            if cliente_existente:
                return jsonify({'success': False, 'error': 'Ya existe un cliente con ese número de identificación'}), 400

        cliente = Cliente(
            nombre=nombre,
            apellido=apellido,
            telefono=telefono or None,
            tipo_identificacion=tipo_identificacion,
            numero_identificacion=numero_identificacion or None,
            limite_credito=limite_credito,
            activo=True,
        )
        db.session.add(cliente)
        db.session.commit()

        return jsonify({
            'success': True,
            'cliente': {
                'id': cliente.id,
                'nombre_completo': cliente.get_nombre_completo(),
                'limite_credito': float(cliente.limite_credito or 0),
                'saldo_pendiente': float(cliente.get_saldo_pendiente() or 0),
            }
        }), 201
    except ValueError:
        return jsonify({'success': False, 'error': 'Límite de crédito inválido'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'Error creando cliente: {str(e)}'}), 500


@ventas_bp.route('/clientes/<int:cliente_id>/actualizar_credito', methods=['POST'])
@login_required
def actualizar_credito_cliente(cliente_id):
    """Actualizar límite de crédito de un cliente"""
    try:
        cliente = Cliente.query.get_or_404(cliente_id)
        limite_credito = float(request.form.get('limite_credito', 0))
        if limite_credito < 0:
            flash('El límite de crédito no puede ser negativo', 'danger')
            return redirect(url_for('ventas.lista_clientes'))
        cliente.limite_credito = limite_credito
        db.session.commit()
        flash(f'Límite de crédito actualizado para {cliente.get_nombre_completo()}', 'success')
        return redirect(url_for('ventas.lista_clientes'))
    except ValueError:
        flash('Error en el valor del límite de crédito', 'danger')
        return redirect(url_for('ventas.lista_clientes'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error actualizando crédito: {str(e)}', 'danger')
        return redirect(url_for('ventas.lista_clientes'))


@ventas_bp.route('/clientes/<int:cliente_id>/cartera')
@login_required
def cartera_cliente(cliente_id):
    """Ver cartera de un cliente específico"""
    cliente = Cliente.query.get_or_404(cliente_id)
    
    # Ventas pendientes
    ventas_pendientes = Venta.query.filter(
        Venta.cliente_id == cliente_id,
        Venta.estado.in_(['pendiente', 'parcial'])
    ).order_by(Venta.fecha_venta.desc()).all()
    
    # Historial de pagos
    pagos = Pago.query.filter_by(cliente_id=cliente_id).order_by(
        Pago.fecha_pago.desc()
    ).limit(10).all()

    total_ventas = sum(float(v.total or 0) for v in ventas_pendientes)
    total_pagado = sum(float(v.get_monto_pagado() or 0) for v in ventas_pendientes)
    total_pendiente = sum(float(v.get_saldo_pendiente() or 0) for v in ventas_pendientes)
    
    return render_template('ventas/cartera_cliente.html',
                         title=f'Cartera - {cliente.get_nombre_completo()}',
                         cliente=cliente,
                         ventas_pendientes=ventas_pendientes,
                         pagos=pagos,
                         cartera_totales={
                             'total_ventas': total_ventas,
                             'total_pagado': total_pagado,
                             'total_pendiente': total_pendiente
                         })


@ventas_bp.route('/pagos/nuevo/<int:venta_id>')
@login_required
def nuevo_pago(venta_id):
    """Formulario para registrar un nuevo pago"""
    venta = Venta.query.get_or_404(venta_id)
    
    if venta.estado == 'completada':
        flash('Esta venta ya está completamente pagada', 'info')
        return redirect(url_for('ventas.cartera_cliente', cliente_id=venta.cliente_id))
    
    saldo_pendiente = venta.get_saldo_pendiente()
    
    return render_template('ventas/nuevo_pago.html',
                         title=f'Nuevo Pago - {venta.numero_venta}',
                         venta=venta,
                         saldo_pendiente=saldo_pendiente)


@ventas_bp.route('/pagos/registrar', methods=['POST'])
@login_required
def registrar_pago():
    """Registrar un nuevo pago"""
    try:
        venta_id = int(request.form.get('venta_id'))
        monto = float(request.form.get('monto'))
        forma_pago = request.form.get('forma_pago')
        referencia = request.form.get('referencia', '').strip()
        observaciones = request.form.get('observaciones', '').strip()
        
        venta = Venta.query.get_or_404(venta_id)
        saldo_pendiente = venta.get_saldo_pendiente()
        
        # Validaciones
        if monto <= 0:
            flash('El monto debe ser mayor a cero', 'danger')
            return redirect(url_for('ventas.nuevo_pago', venta_id=venta_id))
        
        if monto > saldo_pendiente:
            flash(f'El monto no puede ser mayor al saldo pendiente (${saldo_pendiente:.2f})', 'danger')
            return redirect(url_for('ventas.nuevo_pago', venta_id=venta_id))
        
        # Generar número de pago
        numero_pago = f"PAG-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        
        # Resolver usuario receptor válido sin disparar autoflush
        with db.session.no_autoflush:
            receptor = User.query.get(current_user.id)
            if not receptor:
                username = getattr(current_user, 'username', None)
                if username:
                    receptor = User.query.filter_by(username=username).first()
            if not receptor and venta.vendedor_id:
                receptor = User.query.get(venta.vendedor_id)
            if not receptor:
                receptor = User.query.order_by(User.id).first()
        
        if not receptor:
            flash('No se pudo identificar el usuario receptor del pago', 'danger')
            return redirect(url_for('ventas.nuevo_pago', venta_id=venta_id))
        
        # Crear pago
        pago = Pago(
            numero_pago=numero_pago,
            numero_recibo=numero_pago,
            venta_id=venta_id,
            cliente_id=venta.cliente_id,
            recibido_por=receptor.id,
            monto=monto,
            forma_pago=forma_pago,
            referencia=referencia or None,
            observaciones=observaciones or None
        )
        
        db.session.add(pago)
        
        # Actualizar estado de la venta
        venta.actualizar_estado()
        
        db.session.commit()
        
        flash(f'Pago registrado exitosamente. Número: {numero_pago}', 'success')
        return redirect(url_for('ventas.cartera_cliente', cliente_id=venta.cliente_id))
        
    except ValueError:
        flash('Error en los datos proporcionados', 'danger')
        return redirect(url_for('ventas.nuevo_pago', venta_id=request.form.get('venta_id')))
    except Exception as e:
        db.session.rollback()
        flash(f'Error registrando pago: {str(e)}', 'danger')
        return redirect(url_for('ventas.nuevo_pago', venta_id=request.form.get('venta_id')))


@ventas_bp.route('/anular/<int:venta_id>', methods=['POST'])
@login_required
def anular_venta(venta_id):
    """Anular una venta o credito y liberar inventario"""
    if not current_user.has_permission('ventas.sale.cancel'):
        flash('No tienes permisos para anular ventas', 'danger')
        return _redirect_back()

    venta = Venta.query.get_or_404(venta_id)

    if venta.estado == 'cancelada':
        flash(f'La venta {venta.numero_venta} ya se encuentra anulada', 'info')
        return _redirect_back()

    pagos_registrados = Pago.query.filter_by(venta_id=venta.id).count()
    if pagos_registrados > 0:
        flash(
            f'No se puede anular la venta {venta.numero_venta} porque tiene {pagos_registrados} pago(s) registrado(s).',
            'danger'
        )
        return _redirect_back()

    try:
        detalles = DetalleVenta.query.filter_by(venta_id=venta.id).all()
        for detalle in detalles:
            huevos_a_liberar = Huevo.query.filter(
                Huevo.categoria_id == detalle.categoria_id,
                Huevo.roto == False,
                Huevo.vendido == True
            ).order_by(
                Huevo.fecha_venta.desc(),
                Huevo.id.desc()
            ).limit(detalle.cantidad_huevos).all()

            if len(huevos_a_liberar) < detalle.cantidad_huevos:
                categoria = CategoriaHuevo.query.get(detalle.categoria_id)
                nombre_categoria = categoria.nombre if categoria else str(detalle.categoria_id)
                raise ValueError(
                    f'No fue posible liberar inventario suficiente para la categoria {nombre_categoria}.'
                )

            for huevo in huevos_a_liberar:
                huevo.vendido = False
                huevo.fecha_venta = None

        motivo = (request.form.get('motivo') or '').strip()
        sello = f'ANULADA {datetime.now().strftime("%Y-%m-%d %H:%M")}'
        if motivo:
            sello += f' Motivo: {motivo}'
        venta.observaciones = f'{(venta.observaciones or "").strip()} | {sello}'.strip(' |')
        venta.estado = 'cancelada'

        db.session.commit()
        flash(f'Venta {venta.numero_venta} anulada correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al anular la venta: {str(e)}', 'danger')

    return _redirect_back()


# ===========================
# APIs PARA EL FRONTEND
# ===========================

@ventas_bp.route('/api/ventas/inventario')
@login_required
def api_inventario_ventas():
    """API para obtener inventario disponible para ventas"""
    inventario = db.session.query(
        CategoriaHuevo.id,
        CategoriaHuevo.nombre,
        CategoriaHuevo.precio_venta,
        func.count(Huevo.id).label('cantidad_disponible')
    ).join(
        Huevo, CategoriaHuevo.id == Huevo.categoria_id
    ).filter(
        Huevo.roto == False,
        Huevo.vendido == False,
        CategoriaHuevo.activo == True
    ).group_by(
        CategoriaHuevo.id, CategoriaHuevo.nombre, CategoriaHuevo.precio_venta
    ).all()
    
    return jsonify([{
        'id': item.id,
        'nombre': item.nombre,
        'precio_base': float(item.precio_venta),
        'cantidad_disponible': item.cantidad_disponible,
        'paneles_disponibles': item.cantidad_disponible // 30
    } for item in inventario])


@ventas_bp.route('/api/clientes/buscar')
@login_required
def api_buscar_clientes():
    """API para buscar clientes"""
    search = request.args.get('q', '').strip()
    
    if not search or len(search) < 2:
        return jsonify([])
    
    # Usar ilike para búsqueda case-insensitive
    search_pattern = f'%{search}%'
    
    clientes = Cliente.query.filter(
        Cliente.activo == True,
        or_(
            Cliente.nombre.ilike(search_pattern),
            Cliente.apellido.ilike(search_pattern),
            Cliente.numero_identificacion.ilike(search_pattern)
        )
    ).limit(10).all()
    
    return jsonify([{
        'id': cliente.id,
        'nombre_completo': cliente.get_nombre_completo(),
        'numero_identificacion': cliente.numero_identificacion,
        'limite_credito': float(cliente.limite_credito),
        'saldo_pendiente': cliente.get_saldo_pendiente(),
        'puede_comprar': cliente.limite_credito > cliente.get_saldo_pendiente()
    } for cliente in clientes])
