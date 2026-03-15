import logging

from dotenv import load_dotenv

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
            existing = Anchor.query.filter_by(douyin_id=douyin_id).first()
            payload = {
                'name': name,
                'room_id': item.get('room_id'),
                'avatar_url': item.get('avatar_url'),
                'is_followed': item.get('is_followed', True),
            }

            if existing:
                changed = False
                for field, value in payload.items():
                    if getattr(existing, field) != value:
                        setattr(existing, field, value)
                        changed = True
                if changed:
                    updated += 1
            else:
                db.session.add(Anchor(douyin_id=douyin_id, **payload))
                created += 1

        db.session.flush()

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


anchor_sync_service = AnchorSyncService()
