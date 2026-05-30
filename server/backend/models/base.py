from sqlalchemy.orm import DeclarativeBase, declared_attr
import re

# Hàm tự động đổi tên class (CamelCase) thành tên bảng (snake_case)
def camel_to_snake(name: str) -> str:
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()

class Base(DeclarativeBase):
    """
    Lớp gốc cho mọi bảng trong Database.
    @declared_attr:
        Tu dong hoa dat ten bang
        cls -> camel_to_snake -> cls_tabel
        vd: CalendarEvent -> bang calendar_events trong SQLite 
    """
    @declared_attr #Phuong thuc cua lop
    def __tablename__(cls) -> str:
        return camel_to_snake(cls.__name__) + "s"