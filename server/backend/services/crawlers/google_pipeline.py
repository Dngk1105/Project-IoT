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
            creds = flow.run_local_server(port=0)
        
        
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
    async with AsyncSessionLocal() as db:
        try:
            logger.info("Dang don dep lich Google cu trong Database...")
            await clear_future_events_by_source(db, EventSource.GOOGLE)

            for item in events_data:
                start_raw = item['start'].get('dateTime', item['start'].get('date'))
                end_raw = item['end'].get('dateTime', item['end'].get('date'))
                
                if not start_raw or 'T' not in start_raw:
                    continue
                
                # ve datetime Python
                start_dt = datetime.fromisoformat(start_raw)
                end_dt = datetime.fromisoformat(end_raw)

                event_in = CalendarEventCreate(
                    summary=item.get('summary', 'Khong tieu de'),
                    description=item.get('description', ''),
                    location=item.get('location', ''),
                    start_time=start_dt,
                    end_time=end_dt,
                    is_recurring=False, # Đã bung sẵn nên không cần rrule
                    source=EventSource.GOOGLE
                )
                

                result = await create_event(db, event_in)
                if result:
                    success_count += 1
            
            logger.info(f"Hoan tat! Da nap {success_count} su kien tu Google vao Database.")
        except Exception as e:
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