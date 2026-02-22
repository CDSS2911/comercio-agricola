from flask import render_template, current_app
from flask_mail import Message
from app import mail


def send_email(subject, sender, recipients, text_body, html_body):
    """Función genérica para enviar emails"""
    try:
        msg = Message(subject, sender=sender, recipients=recipients)
        msg.body = text_body
        msg.html = html_body
        mail.send(msg)
        print(f"✅ Email enviado correctamente a {recipients}")
    except Exception as e:
        print(f"❌ Error al enviar email: {e}")
        print("📧 CONTENIDO DEL EMAIL QUE NO SE PUDO ENVIAR:")
        print(f"Para: {recipients}")
        print(f"De: {sender}")
        print(f"Asunto: {subject}")
        print("-"*40)
        print("CONTENIDO TEXTO:")
        print(text_body)
        print("-"*40)
        raise


def send_password_reset_email(user):
    """Enviar email de recuperación de contraseña"""
    token = user.generate_reset_token()
    send_email('[Sistema de Gestión] Recuperación de Contraseña',
               sender=current_app.config['MAIL_DEFAULT_SENDER'],
               recipients=[user.email],
               text_body=render_template('email/reset_password.txt',
                                       user=user, token=token),
               html_body=render_template('email/reset_password.html',
                                       user=user, token=token))


def send_confirmation_email(user):
    """Enviar email de confirmación de cuenta"""
    token = user.generate_confirmation_token()
    send_email('[Sistema de Gestión] Confirma tu cuenta',
               sender=current_app.config['MAIL_DEFAULT_SENDER'],
               recipients=[user.email],
               text_body=render_template('email/confirm_email.txt',
                                       user=user, token=token),
               html_body=render_template('email/confirm_email.html',
                                       user=user, token=token))