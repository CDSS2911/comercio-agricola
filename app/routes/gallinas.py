from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import db, LoteGallinas, RegistroMortalidad, VentaGallinas, RegistroSanitario, LoteRecoleccion, SeparacionGallinas
from app.utils.excel import create_excel_response, create_excel_multisheet_response
from sqlalchemy import func, desc
from datetime import datetime, timedelta, time as datetime_time, date
from werkzeug.utils import secure_filename
from PIL import Image
import os

gallinas_bp = Blueprint('gallinas', __name__, url_prefix='/gallinas')

# Configuración de imágenes
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_IMAGE_DIMENSION = 1920  # Ancho/alto máximo en píxeles

def allowed_file(filename):
    """Verifica si el archivo tiene una extensión permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def compress_image(input_path, output_path, max_dimension=MAX_IMAGE_DIMENSION, quality=85):
    """
    Comprime una imagen reduciendo su tamaño y dimensiones
    
    Args:
        input_path: Ruta de la imagen original
        output_path: Ruta donde se guardará la imagen comprimida
        max_dimension: Dimensión máxima (ancho o alto) en píxeles
        quality: Calidad de compresión JPEG (1-100)
    """
    try:
        with Image.open(input_path) as img:
            # Convertir RGBA a RGB si es necesario
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            
            # Redimensionar si es necesario
            width, height = img.size
            if width > max_dimension or height > max_dimension:
                if width > height:
                    new_width = max_dimension
                    new_height = int(height * (max_dimension / width))
                else:
                    new_height = max_dimension
                    new_width = int(width * (max_dimension / height))
                
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Guardar con compresión
            img.save(output_path, 'JPEG', quality=quality, optimize=True)
            return True
    except Exception as e:
        print(f"Error al comprimir imagen: {str(e)}")
        return False

@gallinas_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal de gestión de gallinas"""
    # Obtener todos los lotes con su información de alertas
    lotes = LoteGallinas.query.filter_by(estado='Activo').order_by(desc(LoteGallinas.fecha_ingreso)).all()
    
    # Agregar información de alertas a cada lote
    lotes_info = []
    for lote in lotes:
        edad_actual = lote.get_edad_actual_semanas()  # Edad total del lote
        semanas_produccion = lote.get_semanas_produccion()  # Semanas desde que empezó a producir
        semanas_restantes = lote.get_semanas_restantes()
        nivel_alerta = lote.get_alerta_nivel()
        mortalidad_total = lote.get_mortalidad_total()
        tasa_mortalidad = (mortalidad_total / lote.cantidad_inicial * 100) if lote.cantidad_inicial > 0 else 0
        
        lotes_info.append({
            'lote': lote,
            'edad_actual': edad_actual,
            'semanas_produccion': semanas_produccion,
            'semanas_restantes': semanas_restantes,
            'nivel_alerta': nivel_alerta,
            'mortalidad_total': mortalidad_total,
            'tasa_mortalidad': round(tasa_mortalidad, 2)
        })
    
    # Estadísticas generales
    total_gallinas = sum([lote.cantidad_actual for lote in lotes])
    lotes_criticos = len([l for l in lotes_info if l['nivel_alerta'] == 'CRITICO'])
    lotes_altos = len([l for l in lotes_info if l['nivel_alerta'] == 'ALTO'])
    
    return render_template('gallinas/dashboard.html',
                         lotes=lotes_info,
                         total_gallinas=total_gallinas,
                         lotes_criticos=lotes_criticos,
                         lotes_altos=lotes_altos)

@gallinas_bp.route('/nuevo_lote', methods=['GET', 'POST'])
@login_required
def nuevo_lote():
    """Crear un nuevo lote de gallinas"""
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            numero_lote = request.form.get('numero_lote')
            cantidad_inicial = int(request.form.get('cantidad_inicial'))
            raza = request.form.get('raza')
            fecha_ingreso = datetime.strptime(request.form.get('fecha_ingreso'), '%Y-%m-%d').date()
            edad_semanas_ingreso = int(request.form.get('edad_semanas_ingreso'))
            ubicacion = request.form.get('ubicacion', '')
            costo_unitario = float(request.form.get('costo_unitario', 0))
            observaciones = request.form.get('observaciones', '')
            
            # Calcular costo total
            costo_total = cantidad_inicial * costo_unitario
            
            # Crear nuevo lote
            nuevo_lote = LoteGallinas(
                numero_lote=numero_lote,
                cantidad_inicial=cantidad_inicial,
                cantidad_actual=cantidad_inicial,
                raza=raza,
                fecha_ingreso=fecha_ingreso,
                edad_semanas_ingreso=edad_semanas_ingreso,
                semanas_produccion_maximas=80,  # Por defecto 80 semanas
                estado='Activo',
                ubicacion=ubicacion,
                costo_unitario=costo_unitario,
                costo_total=costo_total,
                observaciones=observaciones,
                usuario_id=current_user.id
            )
            
            db.session.add(nuevo_lote)
            db.session.commit()
            
            flash(f'Lote {numero_lote} creado exitosamente con {cantidad_inicial} gallinas', 'success')
            return redirect(url_for('gallinas.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear el lote: {str(e)}', 'error')
    
    today = date.today().strftime('%Y-%m-%d')
    return render_template('gallinas/nuevo_lote.html', today=today)

@gallinas_bp.route('/detalle/<int:lote_id>')
@login_required
def detalle_lote(lote_id):
    """Ver detalles de un lote de gallinas"""
    lote = LoteGallinas.query.get_or_404(lote_id)
    
    # Obtener información de producción semanal
    recolecciones = db.session.query(
        LoteRecoleccion.semana_produccion,
        func.count(LoteRecoleccion.id).label('recolecciones'),
        func.sum(LoteRecoleccion.total_huevos).label('total_huevos')
    ).filter(
        LoteRecoleccion.lote_gallinas_id == lote_id
    ).group_by(
        LoteRecoleccion.semana_produccion
    ).order_by(
        LoteRecoleccion.semana_produccion
    ).all()
    
    # Obtener registros de mortalidad
    mortalidades = RegistroMortalidad.query.filter_by(lote_gallinas_id=lote_id)\
        .order_by(desc(RegistroMortalidad.fecha_registro)).all()
    
    # Obtener registros sanitarios
    registros_sanitarios = RegistroSanitario.query.filter_by(lote_gallinas_id=lote_id)\
        .order_by(desc(RegistroSanitario.fecha_aplicacion)).all()
    
    # Obtener ventas de gallinas
    ventas = VentaGallinas.query.filter_by(lote_gallinas_id=lote_id)\
        .order_by(desc(VentaGallinas.fecha_venta)).all()
    
    # Calcular estadísticas
    semanas_produccion = lote.get_semanas_produccion()
    semanas_restantes = lote.get_semanas_restantes()
    nivel_alerta = lote.get_alerta_nivel()
    mortalidad_total = lote.get_mortalidad_total()
    tasa_mortalidad = (mortalidad_total / lote.cantidad_inicial * 100) if lote.cantidad_inicial > 0 else 0
    
    # Calcular producción promedio por semana
    total_huevos = sum([r.total_huevos or 0 for r in recolecciones])
    produccion_promedio = total_huevos / semanas_produccion if semanas_produccion > 0 else 0
    
    # Obtener separaciones de gallinas
    separaciones = SeparacionGallinas.query.filter_by(lote_gallinas_id=lote_id)\
        .order_by(desc(SeparacionGallinas.fecha_separacion)).all()
    
    # Filtrar separaciones por estado
    separaciones_activas = [s for s in separaciones if s.estado == 'Separada']
    separaciones_recuperadas = [s for s in separaciones if s.estado == 'Recuperada']
    separaciones_muertas = [s for s in separaciones if s.estado == 'Muerta']
    separaciones_vendidas = [s for s in separaciones if s.estado == 'Vendida']
    
    return render_template('gallinas/detalle_lote.html',
                         lote=lote,
                         semanas_produccion=semanas_produccion,
                         semanas_restantes=semanas_restantes,
                         nivel_alerta=nivel_alerta,
                         mortalidad_total=mortalidad_total,
                         tasa_mortalidad=round(tasa_mortalidad, 2),
                         produccion_promedio=round(produccion_promedio, 2),
                         recolecciones=recolecciones,
                         mortalidades=mortalidades,
                         registros_sanitarios=registros_sanitarios,
                         ventas=ventas,
                         separaciones=separaciones,
                         separaciones_activas=separaciones_activas,
                         separaciones_recuperadas=separaciones_recuperadas,
                         separaciones_muertas=separaciones_muertas,
                         separaciones_vendidas=separaciones_vendidas,
                         datetime=datetime)

@gallinas_bp.route('/registrar_mortalidad/<int:lote_id>', methods=['GET', 'POST'])
@login_required
def registrar_mortalidad(lote_id):
    """Registrar mortalidad en un lote"""
    lote = LoteGallinas.query.get_or_404(lote_id)
    
    if request.method == 'POST':
        try:
            cantidad = int(request.form.get('cantidad'))
            causa = request.form.get('causa')
            fecha_registro = datetime.strptime(request.form.get('fecha_registro'), '%Y-%m-%d').date()
            observaciones = request.form.get('observaciones', '')
            
            # Campos de separación de gallinas
            gallinas_separadas = int(request.form.get('gallinas_separadas', 0))
            ubicacion_separacion = request.form.get('ubicacion_separacion', '')
            
            # Validar cantidad
            total_afectadas = cantidad + gallinas_separadas
            if total_afectadas > lote.cantidad_actual:
                flash('La cantidad total (muertas + separadas) no puede ser mayor a la cantidad actual de gallinas', 'error')
                return redirect(url_for('gallinas.registrar_mortalidad', lote_id=lote_id))
            
            # Manejo de imagen con validación y compresión
            imagen_filename = None
            if 'imagen' in request.files:
                file = request.files['imagen']
                if file and file.filename:
                    # Validar extensión
                    if not allowed_file(file.filename):
                        flash('Tipo de archivo no permitido. Use: jpg, jpeg, png, gif, webp', 'error')
                        return redirect(url_for('gallinas.registrar_mortalidad', lote_id=lote_id))
                    
                    # Validar tamaño (5 MB máximo)
                    file.seek(0, os.SEEK_END)
                    file_size = file.tell()
                    file.seek(0)
                    
                    if file_size > MAX_IMAGE_SIZE:
                        flash(f'La imagen es muy grande. Tamaño máximo: {MAX_IMAGE_SIZE // (1024*1024)} MB', 'error')
                        return redirect(url_for('gallinas.registrar_mortalidad', lote_id=lote_id))
                    
                    # Generar nombre único con extensión .jpg (siempre)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    imagen_filename = f'mortalidad_{lote_id}_{timestamp}.jpg'
                    
                    # Crear directorio si no existe
                    upload_dir = os.path.join('app', 'static', 'Imagenes', 'gallinas')
                    os.makedirs(upload_dir, exist_ok=True)
                    
                    # Guardar imagen temporalmente
                    temp_path = os.path.join(upload_dir, f'temp_{imagen_filename}')
                    final_path = os.path.join(upload_dir, imagen_filename)
                    
                    try:
                        file.save(temp_path)
                        # Comprimir y redimensionar imagen
                        if compress_image(temp_path, final_path):
                            # Eliminar archivo temporal
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                        else:
                            # Si falla la compresión, usar la imagen original
                            os.rename(temp_path, final_path)
                            flash('La imagen se guardó sin comprimir', 'warning')
                    except Exception as e:
                        flash(f'Error al guardar la imagen: {str(e)}', 'error')
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                        imagen_filename = None
            
            # Crear registro de mortalidad
            registro = RegistroMortalidad(
                lote_gallinas_id=lote_id,
                cantidad=cantidad,
                causa=causa,
                fecha_registro=fecha_registro,
                observaciones=observaciones,
                gallinas_separadas=gallinas_separadas,
                ubicacion_separacion=ubicacion_separacion if gallinas_separadas > 0 else None,
                imagen=imagen_filename,
                usuario_id=current_user.id
            )
            
            # Actualizar cantidad actual del lote (solo restar las muertas, no las separadas)
            lote.cantidad_actual -= cantidad
            
            db.session.add(registro)
            db.session.commit()
            
            mensaje = f'Mortalidad registrada: {cantidad} gallinas muertas'
            if gallinas_separadas > 0:
                mensaje += f', {gallinas_separadas} separadas'
            flash(mensaje, 'success')
            return redirect(url_for('gallinas.detalle_lote', lote_id=lote_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar mortalidad: {str(e)}', 'error')
    
    today = date.today().strftime('%Y-%m-%d')
    return render_template('gallinas/registrar_mortalidad.html', lote=lote, today=today)

@gallinas_bp.route('/vender_gallinas/<int:lote_id>', methods=['GET', 'POST'])
@login_required
def vender_gallinas(lote_id):
    """Registrar venta de gallinas de un lote"""
    lote = LoteGallinas.query.get_or_404(lote_id)
    
    if request.method == 'POST':
        try:
            cantidad = int(request.form.get('cantidad'))
            precio_unitario = float(request.form.get('precio_unitario'))
            fecha_venta = datetime.strptime(request.form.get('fecha_venta'), '%Y-%m-%d').date()
            comprador = request.form.get('comprador', '')
            observaciones = request.form.get('observaciones', '')
            
            # Validar cantidad
            if cantidad > lote.cantidad_actual:
                flash('La cantidad a vender no puede ser mayor a la cantidad actual de gallinas', 'error')
                return redirect(url_for('gallinas.vender_gallinas', lote_id=lote_id))
            
            # Calcular precio total
            precio_total = cantidad * precio_unitario
            
            # Crear registro de venta
            venta = VentaGallinas(
                lote_gallinas_id=lote_id,
                cantidad=cantidad,
                precio_unitario=precio_unitario,
                precio_total=precio_total,
                fecha_venta=fecha_venta,
                comprador=comprador,
                observaciones=observaciones,
                usuario_id=current_user.id
            )
            
            # Actualizar cantidad actual del lote
            lote.cantidad_actual -= cantidad
            
            # Si ya no quedan gallinas, marcar lote como finalizado
            if lote.cantidad_actual == 0:
                lote.estado = 'Finalizado'
                lote.fecha_fin_produccion = fecha_venta
            
            db.session.add(venta)
            db.session.commit()
            
            flash(f'Venta registrada: {cantidad} gallinas por ${precio_total:,.0f}', 'success')
            return redirect(url_for('gallinas.detalle_lote', lote_id=lote_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar venta: {str(e)}', 'error')
    
    today = date.today().strftime('%Y-%m-%d')
    return render_template('gallinas/vender_gallinas.html', lote=lote, today=today)

@gallinas_bp.route('/registro_sanitario/<int:lote_id>', methods=['GET', 'POST'])
@login_required
def registro_sanitario(lote_id):
    """Registrar tratamiento sanitario en un lote"""
    lote = LoteGallinas.query.get_or_404(lote_id)
    
    if request.method == 'POST':
        try:
            tipo_tratamiento = request.form.get('tipo_tratamiento')
            producto = request.form.get('producto')
            dosis = request.form.get('dosis', '')
            fecha_aplicacion = datetime.strptime(request.form.get('fecha_aplicacion'), '%Y-%m-%d').date()
            fecha_proxima = request.form.get('fecha_proxima')
            if fecha_proxima:
                fecha_proxima = datetime.strptime(fecha_proxima, '%Y-%m-%d').date()
            else:
                fecha_proxima = None
            observaciones = request.form.get('observaciones', '')
            
            # Campos de separación de gallinas
            gallinas_separadas = int(request.form.get('gallinas_separadas', 0))
            ubicacion_separacion = request.form.get('ubicacion_separacion', '')
            
            # Manejo de imagen con validación y compresión
            imagen_filename = None
            if 'imagen' in request.files:
                file = request.files['imagen']
                if file and file.filename:
                    # Validar extensión
                    if not allowed_file(file.filename):
                        flash('Tipo de archivo no permitido. Use: jpg, jpeg, png, gif, webp', 'error')
                        return redirect(url_for('gallinas.registro_sanitario', lote_id=lote_id))
                    
                    # Validar tamaño (5 MB máximo)
                    file.seek(0, os.SEEK_END)
                    file_size = file.tell()
                    file.seek(0)
                    
                    if file_size > MAX_IMAGE_SIZE:
                        flash(f'La imagen es muy grande. Tamaño máximo: {MAX_IMAGE_SIZE // (1024*1024)} MB', 'error')
                        return redirect(url_for('gallinas.registro_sanitario', lote_id=lote_id))
                    
                    # Generar nombre único con extensión .jpg (siempre)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    imagen_filename = f'sanitario_{lote_id}_{timestamp}.jpg'
                    
                    # Crear directorio si no existe
                    upload_dir = os.path.join('app', 'static', 'Imagenes', 'gallinas')
                    os.makedirs(upload_dir, exist_ok=True)
                    
                    # Guardar imagen temporalmente
                    temp_path = os.path.join(upload_dir, f'temp_{imagen_filename}')
                    final_path = os.path.join(upload_dir, imagen_filename)
                    
                    try:
                        file.save(temp_path)
                        # Comprimir y redimensionar imagen
                        if compress_image(temp_path, final_path):
                            # Eliminar archivo temporal
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                        else:
                            # Si falla la compresión, usar la imagen original
                            os.rename(temp_path, final_path)
                            flash('La imagen se guardó sin comprimir', 'warning')
                    except Exception as e:
                        flash(f'Error al guardar la imagen: {str(e)}', 'error')
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                        imagen_filename = None
            
            # Crear registro sanitario
            registro = RegistroSanitario(
                lote_gallinas_id=lote_id,
                tipo_tratamiento=tipo_tratamiento,
                producto=producto,
                dosis=dosis,
                fecha_aplicacion=fecha_aplicacion,
                fecha_proxima_aplicacion=fecha_proxima,
                observaciones=observaciones,
                gallinas_separadas=gallinas_separadas,
                ubicacion_separacion=ubicacion_separacion if gallinas_separadas > 0 else None,
                imagen=imagen_filename,
                usuario_id=current_user.id
            )
            
            db.session.add(registro)
            db.session.commit()
            
            mensaje = f'Registro sanitario creado: {tipo_tratamiento} - {producto}'
            if gallinas_separadas > 0:
                mensaje += f' ({gallinas_separadas} gallinas separadas)'
            flash(mensaje, 'success')
            return redirect(url_for('gallinas.detalle_lote', lote_id=lote_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear registro sanitario: {str(e)}', 'error')
    
    today = date.today().strftime('%Y-%m-%d')
    return render_template('gallinas/registro_sanitario.html', lote=lote, today=today)

@gallinas_bp.route('/alertas')
@login_required
def alertas():
    """Ver lotes con alertas críticas y altas"""
    lotes = LoteGallinas.query.filter_by(estado='Activo').all()
    
    # Filtrar lotes con alertas críticas o altas
    lotes_alertas = []
    for lote in lotes:
        nivel_alerta = lote.get_alerta_nivel()
        if nivel_alerta in ['CRITICO', 'ALTO']:
            semanas_produccion = lote.get_semanas_produccion()
            semanas_restantes = lote.get_semanas_restantes()
            
            lotes_alertas.append({
                'lote': lote,
                'semanas_produccion': semanas_produccion,
                'semanas_restantes': semanas_restantes,
                'nivel_alerta': nivel_alerta
            })
    
    # Ordenar por nivel de alerta (CRITICO primero)
    lotes_alertas.sort(key=lambda x: (0 if x['nivel_alerta'] == 'CRITICO' else 1, x['semanas_restantes']))
    
    return render_template('gallinas/alertas.html', lotes=lotes_alertas)


@gallinas_bp.route('/export/excel')
@login_required
def export_excel_gallinas():
    """Exportar tablas del modulo gallinas a Excel"""
    tabla = request.args.get('tabla', '').strip()

    if tabla == 'dashboard':
        lotes = LoteGallinas.query.filter_by(estado='Activo').order_by(desc(LoteGallinas.fecha_ingreso)).all()
        rows = []
        for lote in lotes:
            edad_actual = lote.get_edad_actual_semanas()
            semanas_produccion = lote.get_semanas_produccion()
            semanas_restantes = lote.get_semanas_restantes()
            nivel_alerta = lote.get_alerta_nivel()
            mortalidad_total = lote.get_mortalidad_total()
            tasa_mortalidad = (mortalidad_total / lote.cantidad_inicial * 100) if lote.cantidad_inicial > 0 else 0
            rows.append([
                lote.numero_lote,
                lote.cantidad_actual,
                lote.cantidad_inicial,
                lote.ubicacion or '',
                edad_actual,
                semanas_produccion,
                semanas_restantes,
                nivel_alerta,
                mortalidad_total,
                round(tasa_mortalidad, 2),
                lote.fecha_ingreso
            ])
        return create_excel_response(
            'gallinas_dashboard.xlsx',
            'Lotes Activos',
            ['Lote', 'Cantidad Actual', 'Cantidad Inicial', 'Ubicacion', 'Edad Semanas', 'Semanas Produccion', 'Semanas Restantes', 'Alerta', 'Mortalidad', 'Tasa Mortalidad %', 'Fecha Ingreso'],
            rows
        )

    if tabla == 'alertas':
        lotes = LoteGallinas.query.filter_by(estado='Activo').all()
        rows = []
        for lote in lotes:
            nivel_alerta = lote.get_alerta_nivel()
            if nivel_alerta in ['CRITICO', 'ALTO']:
                rows.append([
                    lote.numero_lote,
                    nivel_alerta,
                    lote.raza or '',
                    lote.cantidad_actual,
                    lote.ubicacion or '',
                    lote.get_semanas_produccion(),
                    lote.get_semanas_restantes(),
                    lote.fecha_ingreso
                ])
        return create_excel_response(
            'gallinas_alertas.xlsx',
            'Alertas',
            ['Lote', 'Nivel', 'Raza', 'Cantidad Actual', 'Ubicacion', 'Semanas Produccion', 'Semanas Restantes', 'Fecha Ingreso'],
            rows
        )

    if tabla == 'detalle_lote':
        lote_id = request.args.get('lote_id', type=int)
        lote = LoteGallinas.query.get_or_404(lote_id)
        recolecciones = db.session.query(
            LoteRecoleccion.semana_produccion,
            func.count(LoteRecoleccion.id).label('recolecciones'),
            func.sum(LoteRecoleccion.total_huevos).label('total_huevos')
        ).filter(LoteRecoleccion.lote_gallinas_id == lote_id).group_by(
            LoteRecoleccion.semana_produccion
        ).order_by(LoteRecoleccion.semana_produccion).all()
        rows_recolecciones = [[
            r.semana_produccion,
            r.recolecciones,
            r.total_huevos or 0
        ] for r in recolecciones]
        mortalidades = RegistroMortalidad.query.filter_by(lote_gallinas_id=lote_id).order_by(desc(RegistroMortalidad.fecha_registro)).all()
        rows_mortalidades = [[
            m.fecha_registro,
            m.cantidad,
            m.causa or '',
            m.ubicacion_separacion or '',
            m.observaciones or ''
        ] for m in mortalidades]
        ventas = VentaGallinas.query.filter_by(lote_gallinas_id=lote_id).order_by(desc(VentaGallinas.fecha_venta)).all()
        rows_ventas = [[
            v.fecha_venta,
            v.cantidad,
            float(v.precio_unitario or 0),
            float(v.precio_total or 0),
            v.comprador or '',
            v.observaciones or ''
        ] for v in ventas]
        separaciones = SeparacionGallinas.query.filter_by(lote_gallinas_id=lote_id).order_by(desc(SeparacionGallinas.fecha_separacion)).all()
        rows_separaciones = [[
            s.fecha_separacion,
            s.hora_separacion,
            s.cantidad,
            float(s.peso_promedio or 0) if s.peso_promedio else '',
            s.motivo,
            s.ubicacion,
            s.estado,
            s.observaciones or ''
        ] for s in separaciones]

        return create_excel_multisheet_response(
            f'gallinas_detalle_{lote.numero_lote}.xlsx',
            [
                {
                    'name': 'Produccion Semanal',
                    'headers': ['Semana', 'Recolecciones', 'Total Huevos'],
                    'rows': rows_recolecciones
                },
                {
                    'name': 'Mortalidad',
                    'headers': ['Fecha', 'Cantidad', 'Causa', 'Ubicacion', 'Observaciones'],
                    'rows': rows_mortalidades
                },
                {
                    'name': 'Ventas',
                    'headers': ['Fecha', 'Cantidad', 'Precio Unitario', 'Precio Total', 'Comprador', 'Observaciones'],
                    'rows': rows_ventas
                },
                {
                    'name': 'Separaciones',
                    'headers': ['Fecha', 'Hora', 'Cantidad', 'Peso Promedio', 'Motivo', 'Ubicacion', 'Estado', 'Observaciones'],
                    'rows': rows_separaciones
                }
            ]
        )

    flash('Tipo de tabla no valido para exportar', 'error')
    return redirect(url_for('gallinas.dashboard'))

@gallinas_bp.route('/api/lotes_activos')
@login_required
def api_lotes_activos():
    """API para obtener lotes activos (para usar en formulario de recolección)"""
    lotes = LoteGallinas.query.filter_by(estado='Activo').order_by(desc(LoteGallinas.fecha_ingreso)).all()
    
    lotes_data = []
    for lote in lotes:
        semanas_produccion = lote.get_semanas_produccion()
        semanas_restantes = lote.get_semanas_restantes()
        
        lotes_data.append({
            'id': lote.id,
            'numero_lote': lote.numero_lote,
            'raza': lote.raza,
            'cantidad_actual': lote.cantidad_actual,
            'semana_produccion': semanas_produccion,
            'semanas_restantes': semanas_restantes,
            'fecha_inicio_produccion': lote.fecha_inicio_produccion.isoformat() if lote.fecha_inicio_produccion else None
        })
    
    return jsonify(lotes_data)

@gallinas_bp.route('/finalizar_lote/<int:lote_id>', methods=['POST'])
@login_required
def finalizar_lote(lote_id):
    """Finalizar manualmente un lote"""
    lote = LoteGallinas.query.get_or_404(lote_id)
    
    try:
        lote.estado = 'Finalizado'
        lote.fecha_fin_produccion = datetime.now().date()
        db.session.commit()
        
        flash(f'Lote {lote.numero_lote} finalizado exitosamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al finalizar lote: {str(e)}', 'error')
    
    return redirect(url_for('gallinas.dashboard'))


@gallinas_bp.route('/separar_gallinas/<int:lote_id>', methods=['GET', 'POST'])
@login_required
def separar_gallinas(lote_id):
    """Registrar separación de gallinas"""
    lote = LoteGallinas.query.get_or_404(lote_id)
    
    if request.method == 'POST':
        try:
            cantidad = int(request.form.get('cantidad'))
            fecha_separacion = datetime.strptime(request.form.get('fecha_separacion'), '%Y-%m-%d').date()
            hora_separacion = datetime.strptime(request.form.get('hora_separacion'), '%H:%M').time()
            peso_promedio = request.form.get('peso_promedio')
            motivo = request.form.get('motivo')
            ubicacion = request.form.get('ubicacion')
            observaciones = request.form.get('observaciones', '')
            
            # Validar cantidad
            if cantidad > lote.cantidad_actual:
                flash('La cantidad no puede ser mayor a la cantidad actual de gallinas', 'error')
                return redirect(url_for('gallinas.separar_gallinas', lote_id=lote_id))
            
            # Convertir peso a decimal si existe
            peso_decimal = None
            if peso_promedio:
                try:
                    peso_decimal = float(peso_promedio)
                except ValueError:
                    flash('Peso promedio inválido', 'error')
                    return redirect(url_for('gallinas.separar_gallinas', lote_id=lote_id))
            
            # Manejo de imagen con validación y compresión
            imagen_filename = None
            if 'imagen' in request.files:
                file = request.files['imagen']
                if file and file.filename:
                    # Validar extensión
                    if not allowed_file(file.filename):
                        flash('Tipo de archivo no permitido. Use: jpg, jpeg, png, gif, webp', 'error')
                        return redirect(url_for('gallinas.separar_gallinas', lote_id=lote_id))
                    
                    # Validar tamaño (5 MB máximo)
                    file.seek(0, os.SEEK_END)
                    file_size = file.tell()
                    file.seek(0)
                    
                    if file_size > MAX_IMAGE_SIZE:
                        flash(f'La imagen es muy grande. Tamaño máximo: {MAX_IMAGE_SIZE // (1024*1024)} MB', 'error')
                        return redirect(url_for('gallinas.separar_gallinas', lote_id=lote_id))
                    
                    # Generar nombre único con extensión .jpg (siempre)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    imagen_filename = f'separacion_{lote_id}_{timestamp}.jpg'
                    
                    # Crear directorio si no existe
                    upload_dir = os.path.join('app', 'static', 'Imagenes', 'gallinas')
                    os.makedirs(upload_dir, exist_ok=True)
                    
                    # Guardar imagen temporalmente
                    temp_path = os.path.join(upload_dir, f'temp_{imagen_filename}')
                    final_path = os.path.join(upload_dir, imagen_filename)
                    
                    try:
                        file.save(temp_path)
                        # Comprimir y redimensionar imagen
                        if compress_image(temp_path, final_path):
                            # Eliminar archivo temporal
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                        else:
                            # Si falla la compresión, usar la imagen original
                            os.rename(temp_path, final_path)
                            flash('La imagen se guardó sin comprimir', 'warning')
                    except Exception as e:
                        flash(f'Error al guardar la imagen: {str(e)}', 'error')
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                        imagen_filename = None
            
            # Crear registro de separación
            separacion = SeparacionGallinas(
                lote_gallinas_id=lote_id,
                fecha_separacion=fecha_separacion,
                hora_separacion=hora_separacion,
                cantidad=cantidad,
                peso_promedio=peso_decimal,
                motivo=motivo,
                ubicacion=ubicacion,
                estado='Separada',
                observaciones=observaciones,
                imagen=imagen_filename,
                usuario_id=current_user.id
            )
            
            db.session.add(separacion)
            db.session.commit()
            
            flash(f'Separación registrada: {cantidad} gallinas separadas', 'success')
            return redirect(url_for('gallinas.detalle_lote', lote_id=lote_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar separación: {str(e)}', 'error')
    
    return render_template('gallinas/separar_gallinas.html', lote=lote, datetime=datetime)


@gallinas_bp.route('/resolver_separacion/<int:separacion_id>', methods=['POST'])
@login_required
def resolver_separacion(separacion_id):
    """Resolver una separación (recuperada, muerta, vendida)"""
    separacion = SeparacionGallinas.query.get_or_404(separacion_id)
    lote = LoteGallinas.query.get_or_404(separacion.lote_gallinas_id)
    
    try:
        nuevo_estado = request.form.get('estado')
        fecha_resolucion = datetime.strptime(request.form.get('fecha_resolucion'), '%Y-%m-%d').date()
        observaciones = request.form.get('observaciones_resolucion', '')
        
        # Actualizar estado de la separación
        separacion.estado = nuevo_estado
        separacion.fecha_resolucion = fecha_resolucion
        separacion.observaciones_resolucion = observaciones
        
        # Si el estado es "Muerta", registrar automáticamente en mortalidad
        if nuevo_estado == 'Muerta':
            # Crear registro de mortalidad
            registro_mortalidad = RegistroMortalidad(
                lote_gallinas_id=separacion.lote_gallinas_id,
                cantidad=separacion.cantidad,
                causa=f"Muerte durante separación - {separacion.motivo}",
                fecha_registro=fecha_resolucion,
                observaciones=f"Separadas el {separacion.fecha_separacion.strftime('%d/%m/%Y')} a las {separacion.hora_separacion.strftime('%H:%M')}. "
                             f"Ubicación: {separacion.ubicacion}. "
                             f"Obs. inicial: {separacion.observaciones or 'N/A'}. "
                             f"Obs. resolución: {observaciones or 'N/A'}",
                gallinas_separadas=0,  # Ya no hay separadas, murieron
                ubicacion_separacion=separacion.ubicacion,
                imagen=separacion.imagen,  # Usar la misma imagen
                usuario_id=current_user.id
            )
            
            # Restar del lote la cantidad de gallinas muertas
            lote.cantidad_actual -= separacion.cantidad
            
            db.session.add(registro_mortalidad)
            flash(f'Separación resuelta: {separacion.cantidad} gallinas registradas en mortalidad y restadas del lote', 'warning')
        
        elif nuevo_estado == 'Vendida':
            # Si se vendieron, también restar del lote
            lote.cantidad_actual -= separacion.cantidad
            flash(f'Separación resuelta: {separacion.cantidad} gallinas vendidas y restadas del lote', 'success')
        
        else:
            # Estado "Recuperada" - las gallinas vuelven al lote (no se resta nada)
            flash(f'Separación resuelta: {separacion.cantidad} gallinas recuperadas y devueltas al lote', 'success')
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al resolver separación: {str(e)}', 'error')
    
    return redirect(url_for('gallinas.detalle_lote', lote_id=separacion.lote_gallinas_id))
