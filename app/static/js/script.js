// JavaScript personalizado para el Sistema de Gestión

// Función que se ejecuta cuando el DOM está cargado
document.addEventListener('DOMContentLoaded', function() {
    // Inicializar componentes
    initializeComponents();
    
    // Agregar clases de animación a elementos
    addFadeInAnimations();
    
    // Configurar tooltips de Bootstrap
    initializeTooltips();
});

/**
 * Inicializa componentes personalizados
 */
function initializeComponents() {
    // Auto-ocultar alertas después de 5 segundos
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
    
    // Confirmar acciones de eliminación
    const deleteButtons = document.querySelectorAll('[data-action="delete"]');
    deleteButtons.forEach(function(button) {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const itemName = this.dataset.itemName || 'este elemento';
            if (confirm(`¿Estás seguro de que deseas eliminar ${itemName}?`)) {
                // Si hay un formulario asociado, enviarlo
                const form = this.closest('form');
                if (form) {
                    form.submit();
                } else {
                    // Si no hay formulario, redirigir a la URL
                    window.location.href = this.href;
                }
            }
        });
    });
}

/**
 * Agrega animaciones de aparición gradual
 */
function addFadeInAnimations() {
    const cards = document.querySelectorAll('.card');
    cards.forEach(function(card, index) {
        card.classList.add('fade-in');
        card.style.animationDelay = (index * 0.1) + 's';
    });
}

/**
 * Inicializa tooltips de Bootstrap
 */
function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

/**
 * Valida formularios en tiempo real
 */
function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return;
    
    const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
    inputs.forEach(function(input) {
        input.addEventListener('blur', function() {
            validateField(this);
        });
        
        input.addEventListener('input', function() {
            if (this.classList.contains('is-invalid')) {
                validateField(this);
            }
        });
    });
}

/**
 * Valida un campo individual
 */
function validateField(field) {
    const value = field.value.trim();
    let isValid = true;
    let errorMessage = '';
    
    // Validación requerida
    if (field.hasAttribute('required') && !value) {
        isValid = false;
        errorMessage = 'Este campo es obligatorio.';
    }
    
    // Validación de email
    if (field.type === 'email' && value) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(value)) {
            isValid = false;
            errorMessage = 'Ingresa un email válido.';
        }
    }
    
    // Validación de contraseña
    if (field.type === 'password' && value) {
        if (value.length < 6) {
            isValid = false;
            errorMessage = 'La contraseña debe tener al menos 6 caracteres.';
        }
    }
    
    // Aplicar estilos de validación
    if (isValid) {
        field.classList.remove('is-invalid');
        field.classList.add('is-valid');
    } else {
        field.classList.remove('is-valid');
        field.classList.add('is-invalid');
        showFieldError(field, errorMessage);
    }
    
    return isValid;
}

/**
 * Muestra error en un campo
 */
function showFieldError(field, message) {
    let errorDiv = field.nextElementSibling;
    if (!errorDiv || !errorDiv.classList.contains('invalid-feedback')) {
        errorDiv = document.createElement('div');
        errorDiv.classList.add('invalid-feedback');
        field.parentNode.insertBefore(errorDiv, field.nextSibling);
    }
    errorDiv.textContent = message;
}

/**
 * Muestra notificaciones toast
 */
function showNotification(message, type = 'info') {
    const toastContainer = getOrCreateToastContainer();
    
    const toastId = 'toast-' + Date.now();
    const toastHtml = `
        <div class="toast" id="${toastId}" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="toast-header bg-${type} text-white">
                <i class="fas fa-info-circle me-2"></i>
                <strong class="me-auto">Notificación</strong>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        </div>
    `;
    
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement);
    toast.show();
    
    // Eliminar el toast del DOM después de que se oculte
    toastElement.addEventListener('hidden.bs.toast', function() {
        this.remove();
    });
}

/**
 * Obtiene o crea el contenedor de toasts
 */
function getOrCreateToastContainer() {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.classList.add('toast-container', 'position-fixed', 'top-0', 'end-0', 'p-3');
        container.style.zIndex = '1055';
        document.body.appendChild(container);
    }
    return container;
}

/**
 * Carga contenido de forma asíncrona
 */
function loadContent(url, targetElement) {
    const target = typeof targetElement === 'string' 
        ? document.getElementById(targetElement) 
        : targetElement;
        
    if (!target) {
        console.error('Elemento objetivo no encontrado');
        return;
    }
    
    // Mostrar loading
    target.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Cargando...</span></div></div>';
    
    fetch(url)
        .then(response => response.text())
        .then(html => {
            target.innerHTML = html;
            // Re-inicializar componentes en el nuevo contenido
            initializeComponents();
        })
        .catch(error => {
            console.error('Error al cargar contenido:', error);
            target.innerHTML = '<div class="alert alert-danger">Error al cargar el contenido.</div>';
        });
}

/**
 * Utilidad para copiar texto al portapapeles
 */
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        showNotification('Texto copiado al portapapeles', 'success');
    }).catch(function(err) {
        console.error('Error al copiar:', err);
        showNotification('Error al copiar al portapapeles', 'danger');
    });
}

/**
 * Confirma acción con modal personalizado
 */
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

// Exportar funciones para uso global
window.UserManagement = {
    validateForm,
    validateField,
    showNotification,
    loadContent,
    copyToClipboard,
    confirmAction
};