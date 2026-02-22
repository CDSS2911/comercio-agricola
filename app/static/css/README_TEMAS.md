# 🎨 Sistema de Temas - Configuración de Colores

## Tema Actual: Negro, Rojo y Blanco

El archivo `style.css` está configurado con un sistema de variables CSS que permite cambiar fácilmente todos los colores de la aplicación.

## 📋 Variables Principales

### Colores Primarios
```css
--primary-color: #dc143c;           /* Rojo primario (Crimson) */
--primary-dark: #b01030;            /* Rojo oscuro */
--primary-light: #ff4757;           /* Rojo claro */
```

### Colores Secundarios (Negro)
```css
--secondary-color: #1a1a1a;         /* Negro secundario */
--secondary-dark: #000000;          /* Negro puro */
--secondary-light: #2d2d2d;         /* Gris oscuro */
```

### Colores de Acento (Blanco)
```css
--accent-color: #ffffff;            /* Blanco */
--accent-dark: #f5f5f5;             /* Gris claro */
--accent-light: #ffffff;            /* Blanco puro */
```

## 🎨 Temas Alternativos

### Tema 1: Rojo Más Intenso
```css
--primary-color: #ff0000;           /* Rojo puro */
--primary-dark: #cc0000;            /* Rojo muy oscuro */
--primary-light: #ff3333;           /* Rojo brillante */
```

### Tema 2: Rojo Vino
```css
--primary-color: #8b0000;           /* Rojo oscuro (Dark Red) */
--primary-dark: #660000;            /* Rojo muy oscuro */
--primary-light: #a52a2a;           /* Rojo marrón */
```

### Tema 3: Rojo Neón
```css
--primary-color: #ff073a;           /* Rojo neón */
--primary-dark: #d10030;            /* Rojo neón oscuro */
--primary-light: #ff4d6d;           /* Rojo neón claro */
```

### Tema 4: Grises (para contraste menor)
```css
--secondary-color: #2c2c2c;         /* Gris muy oscuro */
--secondary-dark: #1c1c1c;          /* Gris casi negro */
--secondary-light: #3c3c3c;         /* Gris medio-oscuro */
```

## 🔧 Cómo Cambiar el Tema

### Opción 1: Modificar Variables en style.css
Edita las primeras líneas del archivo `style.css`:

```css
:root {
    /* Cambia estos valores por los del tema que desees */
    --primary-color: #dc143c;
    --primary-dark: #b01030;
    --primary-light: #ff4757;
    /* ... resto de variables */
}
```

### Opción 2: Crear un Archivo de Tema Personalizado
Crea un archivo `theme-custom.css` y sobrescribe las variables:

```css
/* theme-custom.css */
:root {
    --primary-color: #tu-color-aqui;
    --primary-dark: #tu-color-oscuro;
    --primary-light: #tu-color-claro;
}
```

Luego incluye este archivo DESPUÉS de `style.css` en tu template base:

```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
<link rel="stylesheet" href="{{ url_for('static', filename='css/theme-custom.css') }}">
```

## 🎯 Elementos que Cambian Automáticamente

Al modificar las variables CSS, estos elementos se actualizan automáticamente:

- ✅ Navegación (navbar)
- ✅ Botones (primary, secondary, danger, etc.)
- ✅ Tarjetas (cards) y sus bordes
- ✅ Formularios (inputs, selects)
- ✅ Tablas
- ✅ Alertas
- ✅ Badges
- ✅ Barras de progreso
- ✅ Modales
- ✅ Links
- ✅ Scrollbar
- ✅ Selección de texto

## 🌈 Paletas de Colores Recomendadas

### Paleta 1: Elegante
- Primary: `#c41e3a` (Rojo carmesí)
- Secondary: `#0f0f0f` (Negro profundo)
- Accent: `#ffffff` (Blanco puro)

### Paleta 2: Agresiva
- Primary: `#e00000` (Rojo brillante)
- Secondary: `#000000` (Negro absoluto)
- Accent: `#ffffff` (Blanco)

### Paleta 3: Sofisticada
- Primary: `#a01030` (Rojo vino)
- Secondary: `#1a1a1a` (Gris muy oscuro)
- Accent: `#f8f8f8` (Blanco roto)

## 💡 Consejos

1. **Contraste**: Asegúrate de que haya suficiente contraste entre texto y fondo para legibilidad
2. **Consistencia**: Usa las variables en lugar de colores directos en el código
3. **Pruebas**: Prueba el tema en diferentes páginas de la aplicación
4. **Accesibilidad**: Verifica que los colores cumplan con estándares WCAG (mínimo contraste 4.5:1)

## 🛠️ Herramientas Útiles

- **Color Picker**: https://htmlcolorcodes.com/
- **Verificador de Contraste**: https://webaim.org/resources/contrastchecker/
- **Generador de Paletas**: https://coolors.co/
- **Adobe Color**: https://color.adobe.com/

## 📝 Ejemplos de Uso

### Cambiar solo el rojo principal
```css
:root {
    --primary-color: #ff0000; /* Rojo puro */
}
```

### Hacer el fondo más claro
```css
:root {
    --bg-primary: #2d2d2d; /* Gris oscuro en lugar de negro */
    --bg-secondary: #3d3d3d;
}
```

### Ajustar sombras
```css
:root {
    --shadow-md: 0 0.5rem 1rem rgba(255, 0, 0, 0.3); /* Sombra roja más intensa */
}
```
