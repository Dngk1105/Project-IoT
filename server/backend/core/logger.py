import logging
import sys
import unicodedata
import re
from pathlib import Path

#Lam sach text
#Viet Tieng viet khong dau cho do bi loi dinh dang
def clean_text(text: str) -> str:
    if not isinstance(text, str):   #kiem tra text co thuoc kieu str
        return str(text)
    
    #Chuan hoa text unicdoe theo NFKD (Unicode Normalization Form Compatibility Decomposition)
    nfkd_form = unicodedata.normalize('NFKD', text)
    
    #Bo dau
    text_no_accent = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    text_no_accent = text_no_accent.replace('Đ', 'D').replace('đ', 'd')
    
    #regex: [^\w\s\.,;:|/\-\[\]] Xoa cac ki tu khong la /w (chu), /s dau cach,...
    clean_text = re.sub(r'[^\w\s\.,;:|/\-\[\]]', '', text_no_accent)
    
    return clean_text

"""
Lop Formatter duoc su dung de quyet dinh log se duoc in ra nhu the nao.
Ke thua lop Formatter de cho LogRecord (Lop luu tru mot record do logger tao ra)
de di qua ham clean_text truoc khi toi Handler
"""
class CleanAsciiFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        original_msg = record.getMessage()
        record.msg = clean_text(original_msg)
        return super().format(record) #goi lai ham goc de xu li tiep

def get_logger(module_name: str, log_file: str = "system.log") -> logging.Logger:
    """
    Khởi tạo Logger. 
    - module_name: Tên file đang chạy
    - log_file: Tên file vật lý lưu trong thư mục logs/ (default = system.log)
    """
    #Return a logger with the specified name, creating it if necessary.
    logger = logging.getLogger(module_name)
    if logger.hasHandlers():    #Tranh logger duoc tao nhieu lan
        return logger
    logger.propagate = False #Tranh gọi lên logger cha
    logger.setLevel(logging.INFO) #Ghi nhan log tu INFOR->Warning->...
    
    #[Thời gian] | [Mức độ] | [Tên File] - [Nội dung]
    log_format = '%(asctime)s | %(levelname)s | %(name)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    formatter = CleanAsciiFormatter(fmt=log_format, datefmt=date_format)     #formatter da tinh chinh
    
    #log ra console
    #sys.stdout: ghi truc tiep vao buffer
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    
    #log ra file 
    base_dir = Path(__file__).resolve().parent.parent  #ve backend/
    log_dir = base_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True) #tao logs neu chua ton tai

    file_handler = logging.FileHandler(log_dir / log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger