import uuid
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from notifications.models import Notification, NotificationType
from user_management.models import User
from user_management.email_service import email_service

logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    def create_notification(
        db: Session,
        user_id: uuid.UUID,
        type: NotificationType,
        message: str,
        related_application_id: Optional[uuid.UUID] = None,
        send_email: bool = True
    ) -> Notification:
        """
        Create a notification and optionally send email.
        
        Email sending is optional and failure does not break notification creation.
        """
        notification = Notification(
            user_id=user_id,
            type=type,
            message=message,
            related_application_id=related_application_id
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        
        # Attempt to send email if enabled
        if send_email:
            try:
                user = db.query(User).filter_by(id=user_id).first()
                if user and hasattr(user, 'email') and user.email:
                    subject = f"Recruitment Platform - {type.value}"
                    email_sent = email_service.send_email(user.email, subject, message)
                    if email_sent:
                        logger.info(f"Email notification sent to {user.email} for notification {notification.id}")
                    else:
                        logger.warning(f"Failed to send email notification to {user.email}")
                else:
                    logger.debug(f"User {user_id} has no email or email not available, skipping email notification")
            except Exception as e:
                logger.warning(f"Email notification failed for user {user_id}: {e}")
                # Notification already saved, continue despite email failure
        
        return notification

    @staticmethod
    def get_notifications(db: Session, user_id: uuid.UUID) -> List[Notification]:
        return db.query(Notification).filter_by(user_id=user_id).order_by(Notification.created_at.desc()).all()
