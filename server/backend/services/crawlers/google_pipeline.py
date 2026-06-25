import os
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Google lib 
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# local lib
from core.database import AsyncSessionLocal
from core.logger import get_logger
from models.calendar import EventSource
from schemas.calendar import CalendarEventCreate
from crud.calendar import create_event, clear_future_events_by_source

from sqlalchemy import select
from models.calendar import CalendarEvent

logger = get_logger("google_pipeline", log_file="google_sync.log")

# Path 
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'credentials.json')
TOKEN_FILE = os.path.join(BASE_DIR, 'token.json')
TZ = ZoneInfo("Asia/Ho_Chi_Minh")

#Lay du lieu, chay thread rieng
def _sync_fetch_google_events(days_ahead=90):
    """
    Hàm đồng bộ (Synchronous) gọi API Google.
    Cần cho một thread riêng
    """
    creds = None
    # Check tok
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    # Tao tok
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            logger.warning("Chua co Token! Dang nhap Google...")
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(f"Khong tim thay {CREDENTIALS_FILE}. Vui long tai tu Google Cloud!")
            
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=10087)
        
        
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
            logger.info("Da cap quyen Google Calendar thanh cong!")

    # Ket noi Google Server
    service = build('calendar', 'v3', credentials=creds)

    # Gioi han thoi gian
    now = datetime.now(TZ)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=days_ahead)).isoformat()

    logger.info(f"Dang quet lich Google tu {now.date()} den {(now + timedelta(days=days_ahead)).date()}...")
    
    # singleEvents=True: Cac su kien lap lai duoc tinh la mot su kien don le
    events_result = service.events().list(
        calendarId='primary', 
        timeMin=time_min,
        timeMax=time_max, 
        maxResults=200, 
        singleEvents=True, 
        orderBy='startTime'
    ).execute()

    return events_result.get('items', [])

#Parse va luu DB
async def parse_and_load_google_events(events_data: list):
    success_count = 0
    now = datetime.now(TZ)
    
    async with AsyncSessionLocal() as db:
        try:
            logger.info("Dang quet lai Google Events de dong bo Delta...")
            
            # Lấy tất cả sự kiện Google hiện có trong tương lai
            stmt = select(CalendarEvent).where(
                CalendarEvent.source == EventSource.GOOGLE,
                CalendarEvent.start_time >= now
            )
            result = await db.execute(stmt)
            existing_events = {ev.id: ev for ev in result.scalars().all()}
            
            scraped_ids = set()

            # Quét dữ liệu mới (UPSERT)
            for item in events_data:
                gg_id = item.get("id")
                if not gg_id: continue
                
                # Tạo Định danh cố định từ Google ID
                event_id = f"gg_{gg_id}"
                scraped_ids.add(event_id)
                
                start_raw = item['start'].get('dateTime', item['start'].get('date'))
                end_raw = item['end'].get('dateTime', item['end'].get('date'))
                if not start_raw or 'T' not in start_raw: continue
                
                start_dt = datetime.fromisoformat(start_raw)
                end_dt = datetime.fromisoformat(end_raw)
                summary = item.get('summary', 'Khong tieu de')
                desc = item.get('description', '')
                loc = item.get('location', '')

                if event_id in existing_events:
                    # UPDATE: Chỉ gán giá trị mới. SQLAlchemy chỉ tự động đổi updated_at nếu có sự khác biệt!
                    db_ev = existing_events[event_id]
                    db_ev.summary = summary
                    db_ev.description = desc
                    db_ev.location = loc
                    db_ev.start_time = start_dt
                    db_ev.end_time = end_dt
                    db_ev.is_cancelled = False
                else:
                    # INSERT
                    new_ev = CalendarEvent(
                        id=event_id,
                        summary=summary,
                        description=desc,
                        location=loc,
                        start_time=start_dt,
                        end_time=end_dt,
                        source=EventSource.GOOGLE
                    )
                    db.add(new_ev)
                    
                success_count += 1
                
            # Soft Delete: Hủy các sự kiện đã bị xóa trên Google Calendar
            for ev_id, db_ev in existing_events.items():
                if ev_id not in scraped_ids:
                    db_ev.is_cancelled = True

            await db.commit()
            logger.info(f"Hoan tat! Đã đồng bộ {success_count} sự kiện Google.")
        except Exception as e:
            await db.rollback()
            logger.error(f"Loi khi parse Google events: {str(e)}")

# API goi ngoai
async def run_google_sync_pipeline():
    logger.info("--- KICH HOAT PIPELINE DONG BO GOOGLE CALENDAR ---")
    try:
        # Chay thread rieng
        raw_events = await asyncio.to_thread(_sync_fetch_google_events, 90)
        
        if raw_events:
            await parse_and_load_google_events(raw_events)
        else:
            logger.info("Khong co su kien nao trong 90 ngay toi.")
    except Exception as e:
        logger.error(f"Loi Pipeline Google: {str(e)}")

# Test
if __name__ == "__main__":
    from core.database import init_db
    async def test_run():
        await init_db()
        await run_google_sync_pipeline()
    asyncio.run(test_run())