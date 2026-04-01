import logging

from dotenv import load_dotenv
from sqlalchemy.exc import IntegrityError

from app.models import Anchor, db
from app.services.anchor_config_service import anchor_config_service

load_dotenv()

logger = logging.getLogger(__name__)


class AnchorSyncService:
    """Sync fixed anchor config into the runtime database."""

    def sync(self):
        anchors = anchor_config_service.list_anchors()

        created = 0
        updated = 0
        disabled = 0
        configured_ids = set()

        for item in anchors:
            douyin_id = (item.get('douyin_id') or '').strip()
            name = (item.get('name') or '').strip()
            if not douyin_id or not name:
                logger.warning('Skipping invalid anchor config item: %s', item)
                continue

            configured_ids.add(douyin_id)
            payload = {
                'name': name,
                'room_id': item.get('room_id'),
                'avatar_url': item.get('avatar_url'),
                'is_followed': item.get('is_followed', True),
            }

            result = self._upsert_anchor(douyin_id, payload)
            if result == 'created':
                created += 1
            elif result == 'updated':
                updated += 1

        managed_anchors = Anchor.query.all()
        for anchor in managed_anchors:
            if anchor.douyin_id not in configured_ids and anchor.is_followed:
                anchor.is_followed = False
                disabled += 1

        db.session.commit()
        logger.info(
            'Anchor config sync complete: total=%s created=%s updated=%s disabled=%s',
            len(configured_ids),
            created,
            updated,
            disabled
        )
        return {
            'created': created,
            'updated': updated,
            'disabled': disabled,
            'total': len(configured_ids),
        }

    def _apply_payload(self, anchor, payload):
        changed = False
        for field, value in payload.items():
            if getattr(anchor, field) != value:
                setattr(anchor, field, value)
                changed = True
        return changed

    def _upsert_anchor(self, douyin_id, payload):
        existing = Anchor.query.filter_by(douyin_id=douyin_id).first()
        if existing:
            if self._apply_payload(existing, payload):
                db.session.commit()
                return 'updated'
            return 'unchanged'

        db.session.add(Anchor(douyin_id=douyin_id, **payload))
        try:
            db.session.commit()
            return 'created'
        except IntegrityError:
            # Another process may have inserted the same douyin_id concurrently.
            db.session.rollback()
            existing = Anchor.query.filter_by(douyin_id=douyin_id).first()
            if not existing:
                raise
            if self._apply_payload(existing, payload):
                db.session.commit()
                return 'updated'
            return 'unchanged'
        except Exception:
            db.session.rollback()
            raise


anchor_sync_service = AnchorSyncService()
