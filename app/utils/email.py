import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app, render_template


def _bool(value):
    return str(value).strip().lower() in {"true", "1", "on", "yes"}


def _validate_ssl_config():
    server = current_app.config.get("MAIL_SERVER")
    port = int(current_app.config.get("MAIL_PORT") or 0)
    use_ssl = _bool(current_app.config.get("MAIL_USE_SSL"))
    use_tls = _bool(current_app.config.get("MAIL_USE_TLS"))
    username = (current_app.config.get("MAIL_USERNAME") or "").strip()
    password = (current_app.config.get("MAIL_PASSWORD") or "").strip()

    if not server:
        return False, "MAIL_SERVER no definido"
    if port != 465:
        return False, "MAIL_PORT debe ser 465 para SSL estricto"
    if not use_ssl:
        return False, "MAIL_USE_SSL debe estar en true"
    if use_tls:
        return False, "MAIL_USE_TLS debe estar en false con SSL estricto"
    if not username or not password:
        return False, "MAIL_USERNAME/MAIL_PASSWORD no definidos"
    return True, ""


def send_email(subject, sender, recipients, text_body, html_body):
    """Envia correo exclusivamente por SSL (SMTP 465)."""
    ok, reason = _validate_ssl_config()
    if not ok:
        current_app.logger.error("Configuracion SMTP invalida: %s", reason)
        return False

    server = current_app.config["MAIL_SERVER"]
    port = int(current_app.config["MAIL_PORT"])
    username = current_app.config["MAIL_USERNAME"].strip()
    password = current_app.config["MAIL_PASSWORD"].strip()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(server, port, timeout=20, context=context) as smtp:
            smtp.ehlo()
            smtp.login(username, password)
            smtp.send_message(msg)
        current_app.logger.info("Email enviado correctamente a %s", recipients)
        return True
    except smtplib.SMTPAuthenticationError:
        current_app.logger.exception(
            "SMTP auth fallo por SSL: revisa MAIL_USERNAME/MAIL_PASSWORD."
        )
        return False
    except Exception:
        current_app.logger.exception(
            "Error al enviar email por SSL. subject=%s sender=%s recipients=%s",
            subject,
            sender,
            recipients,
        )
        return False


def send_password_reset_email(user):
    token = user.generate_reset_token()
    app_name = current_app.config.get("APP_NAME", "Sistema")
    return send_email(
        f"[{app_name}] Recuperacion de Contrasena",
        sender=current_app.config["MAIL_DEFAULT_SENDER"],
        recipients=[user.email],
        text_body=render_template(
            "email/reset_password.txt", user=user, token=token, app_name=app_name
        ),
        html_body=render_template(
            "email/reset_password.html", user=user, token=token, app_name=app_name
        ),
    )


def send_confirmation_email(user):
    token = user.generate_confirmation_token()
    app_name = current_app.config.get("APP_NAME", "Sistema")
    return send_email(
        f"[{app_name}] Confirma tu cuenta",
        sender=current_app.config["MAIL_DEFAULT_SENDER"],
        recipients=[user.email],
        text_body=render_template(
            "email/confirm_email.txt", user=user, token=token, app_name=app_name
        ),
        html_body=render_template(
            "email/confirm_email.html", user=user, token=token, app_name=app_name
        ),
    )
