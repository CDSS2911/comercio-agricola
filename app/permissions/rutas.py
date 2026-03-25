"""Configuracion centralizada de permisos por endpoint (ruta)."""

# Catalogo de permisos disponibles en el sistema.
# Agrega nuevos permisos aqui para que se sincronicen automaticamente.
PERMISSION_DEFINITIONS = {
    'main.dashboard.view': ('Ver panel de control', 'main', 'Ver panel general con graficos'),
    'admin.panel': ('Acceso panel admin', 'admin', 'Acceder al panel administrativo'),
    'users.view': ('Ver usuarios', 'usuarios', 'Ver listado de usuarios'),
    'users.create': ('Crear usuarios', 'usuarios', 'Crear nuevos usuarios'),
    'users.edit': ('Editar usuarios', 'usuarios', 'Editar usuarios existentes'),
    'users.toggle_active': ('Activar/Inactivar usuarios', 'usuarios', 'Cambiar estado de usuarios'),
    'users.reset_password': ('Resetear contrasenas', 'usuarios', 'Generar contrasenas temporales'),
    'users.assign_roles': ('Asignar roles', 'usuarios', 'Asignar roles a usuarios'),
    'roles.manage': ('Gestionar roles', 'usuarios', 'CRUD de roles'),
    'permissions.manage': ('Gestionar permisos', 'usuarios', 'CRUD de permisos'),
    'inventario.access': ('Acceso inventario', 'inventario', 'Acceder a inventario de huevos'),
    'inventario.config': ('Configurar inventario', 'inventario', 'Administrar categorias y pesas'),
    'gallinas.novedades': ('Registrar novedades aves', 'gallinas', 'Gestionar novedades de gallinas'),
    # Legacy (se conserva por compatibilidad)
    'ventas.sell': ('Vender (legacy)', 'ventas', 'Permiso legacy de ventas'),
    # Ventas granulares
    'ventas.dashboard.view': ('Ver dashboard ventas', 'ventas', 'Ver panel principal de ventas'),
    'ventas.sale.create': ('Crear ventas', 'ventas', 'Registrar nuevas ventas'),
    'ventas.history.view': ('Ver historial de ventas', 'ventas', 'Consultar historial y detalle de ventas'),
    'ventas.clients.view': ('Ver clientes', 'ventas', 'Ver listado y cartera de clientes'),
    'ventas.clients.manage': ('Gestionar clientes', 'ventas', 'Crear/editar credito de clientes'),
    'ventas.payments.manage': ('Gestionar pagos', 'ventas', 'Registrar pagos de ventas a credito'),
    'ventas.sale.cancel': ('Anular ventas', 'ventas', 'Anular ventas y liberar inventario'),
    'ventas.export': ('Exportar ventas', 'ventas', 'Descargar reportes de ventas en Excel'),
}


# Mapa endpoint Flask -> permiso requerido
# Endpoint es "{blueprint}.{funcion}".
ENDPOINT_PERMISSIONS = {
    # Main
    'main.dashboard': 'main.dashboard.view',

    # Inventario (acceso general)
    'inventario.dashboard': 'inventario.access',
    'inventario.lotes': 'inventario.access',
    'inventario.nuevo_lote': 'inventario.access',
    'inventario.pesar_huevos': 'inventario.access',
    'inventario.ver_detalle_lote': 'inventario.access',
    'inventario.movimientos_combinados': 'inventario.access',
    'inventario.exportar_movimientos_excel': 'inventario.access',
    # Inventario (configuracion)
    'inventario.categorias': 'inventario.config',
    'inventario.crear_categoria': 'inventario.config',
    'inventario.obtener_categoria': 'inventario.config',
    'inventario.actualizar_categoria': 'inventario.config',
    'inventario.cambiar_estado_categoria': 'inventario.config',
    'inventario.pesas': 'inventario.config',
    'inventario.crear_pesa': 'inventario.config',
    'inventario.obtener_pesa': 'inventario.config',
    'inventario.actualizar_pesa': 'inventario.config',
    'inventario.cambiar_estado_pesa': 'inventario.config',
    'inventario.gastos': 'inventario.config',
    'inventario.crear_gasto': 'inventario.config',
    'inventario.actualizar_gasto': 'inventario.config',
    'inventario.eliminar_gasto': 'inventario.config',
    'inventario.exportar_gastos_excel': 'inventario.config',

    # Gallinas
    'gallinas.dashboard': 'gallinas.novedades',
    'gallinas.nuevo_lote': 'gallinas.novedades',
    'gallinas.detalle_lote': 'gallinas.novedades',
    'gallinas.registrar_mortalidad': 'gallinas.novedades',
    'gallinas.separar_gallinas': 'gallinas.novedades',
    'gallinas.alertas': 'gallinas.novedades',
    'gallinas.vender_gallinas': 'gallinas.novedades',
    'gallinas.registro_sanitario': 'gallinas.novedades',
    'gallinas.export_excel_gallinas': 'gallinas.novedades',

    # Ventas
    'ventas.ventas_dashboard': ('ventas.dashboard.view', 'ventas.sell'),
    'ventas.nueva_venta': ('ventas.sale.create', 'ventas.sell'),
    'ventas.procesar_venta': ('ventas.sale.create', 'ventas.sell'),
    'ventas.historial_ventas': ('ventas.history.view', 'ventas.sell'),
    'ventas.detalle_venta': ('ventas.history.view', 'ventas.sell'),
    'ventas.lista_clientes': ('ventas.clients.view', 'ventas.sell'),
    'ventas.cartera_cliente': ('ventas.clients.view', 'ventas.sell'),
    'ventas.nuevo_cliente': 'ventas.clients.manage',
    'ventas.crear_cliente': 'ventas.clients.manage',
    'ventas.actualizar_credito_cliente': 'ventas.clients.manage',
    'ventas.nuevo_pago': 'ventas.payments.manage',
    'ventas.registrar_pago': 'ventas.payments.manage',
    'ventas.anular_venta': 'ventas.sale.cancel',
    'ventas.export_excel_ventas': 'ventas.export',
}


# Roles base para seed automatico.
SYSTEM_ROLE_PERMISSIONS = {
    'superadmin': list(PERMISSION_DEFINITIONS.keys()),
    'admin': [
        'main.dashboard.view',
        'admin.panel',
        'users.view',
        'users.edit',
        'users.toggle_active',
        'users.assign_roles',
        'inventario.access',
        'inventario.config',
        'gallinas.novedades',
        'ventas.dashboard.view',
        'ventas.sale.create',
        'ventas.history.view',
        'ventas.clients.view',
        'ventas.clients.manage',
        'ventas.payments.manage',
        'ventas.sale.cancel',
        'ventas.export',
    ],
    'operador': [
        'inventario.access',
        'gallinas.novedades',
        'ventas.sale.create',
    ],
}
