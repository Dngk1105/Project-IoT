# Workflow Git & GitHub cho Dự Án 2 Người

## Mục tiêu

Workflow này giúp:

- Làm việc nhóm không ghi đè code nhau
- Quản lý source code rõ ràng
- Dễ rollback khi có lỗi
- Dễ review code
- Hạn chế conflict
- Tạo quy trình làm việc chuyên nghiệp

---

# 1. Mô hình branch

Dự án sử dụng mô hình đơn giản:

```text
main
feature/<ten-feature>
```

Ví dụ:

```text
main
feature/login
feature/player-api
feature/dashboard-ui
feature/socketio
```

---

# 2. Nguyên tắc làm việc

## Không commit trực tiếp lên `main`

Tất cả thay đổi phải đi qua:

```text
feature branch -> Pull Request -> main
```

---

## Một tính năng = một branch

Sai:

```text
feature/login-and-dashboard
```

Đúng:

```text
feature/login
feature/dashboard
```

---

## Luôn pull trước khi code

Trước khi bắt đầu làm việc:

```bash
git checkout main
git pull origin main
```

---

## Commit rõ ràng

Sai:

```text
update
fix
aaaa
```

Đúng:

```text
feat: add login API
fix: validate password
docs: update README
```

---

# 3. Khởi tạo dự án

## Clone repository

```bash
git clone https://github.com/username/project.git
```

Di chuyển vào project:

```bash
cd project
```

---

# 4. Workflow chuẩn

## Bước 1 — Cập nhật source mới nhất

```bash
git checkout main
git pull origin main
```

---

## Bước 2 — Tạo branch feature

Ví dụ làm login:

```bash
git checkout -b feature/login
```

---

## Bước 3 — Code

Thực hiện chỉnh sửa source code.

---

## Bước 4 — Kiểm tra thay đổi

```bash
git status
```

---

## Bước 5 — Add file

Add toàn bộ:

```bash
git add .
```

Hoặc add từng file:

```bash
git add app.py
```

---

## Bước 6 — Commit

```bash
git commit -m "feat: add login API"
```

---

## Bước 7 — Push branch

```bash
git push origin feature/login
```

---

## Bước 8 — Tạo Pull Request

Trên GitHub:

```text
feature/login -> main
```

Mô tả PR nên gồm:

- Đã làm gì
- Đã test chưa
- Có known bug không

---

## Bước 9 — Review code

Người còn lại sẽ:

- Kiểm tra logic
- Kiểm tra naming
- Kiểm tra bug
- Kiểm tra format code

Nếu ổn:

```text
Approve -> Merge
```

---

# 5. Workflow thực tế

## Thành viên A

Cập nhật code:

```bash
git checkout main
git pull origin main
```

Tạo branch:

```bash
git checkout -b feature/login
```

Code xong:

```bash
git add .
git commit -m "feat: add login page"

git push origin feature/login
```

Tạo Pull Request:

```text
feature/login -> main
```

---

## Thành viên B

Review Pull Request:

- Approve nếu OK
- Request changes nếu có lỗi

Sau đó merge.

---

## Sau khi merge

Tất cả cập nhật lại source:

```bash
git checkout main
git pull origin main
```

---

# 6. Đồng bộ branch khi main thay đổi

Nếu đang làm dở nhưng `main` đã có update mới:

## Cập nhật main

```bash
git checkout main
git pull origin main
```

---

## Quay lại feature branch

```bash
git checkout feature/login
```

---

## Merge main vào feature

```bash
git merge main
```

---

# 7. Conflict

## Conflict là gì?

Xảy ra khi 2 người sửa cùng một đoạn code.

Ví dụ:

```text
<<<<<<< HEAD
Code của bạn
=======
Code người kia
>>>>>>> main
```

---

## Cách xử lý

1. Chỉnh sửa thủ công
2. Giữ code đúng
3. Xóa marker conflict
4. Commit lại

```bash
git add .
git commit -m "fix: resolve merge conflict"
```

---

# 8. Quy tắc đặt tên branch

Format:

```text
feature/<ten-feature>
```

Ví dụ:

```text
feature/login
feature/player-api
feature/socketio
feature/dashboard-ui
feature/auth
```

---

# 9. Quy tắc commit message

Format chuẩn:

```text
<type>: <description>
```

---

## Các type phổ biến

| Type | Ý nghĩa |
|---|---|
| feat | Thêm tính năng |
| fix | Sửa bug |
| docs | Tài liệu |
| refactor | Tối ưu code |
| style | Format code |
| test | Viết test |

---

## Ví dụ commit tốt

```text
feat: add JWT authentication
fix: validate email format
docs: update installation guide
refactor: optimize database query
```

---

# 10. Những điều KHÔNG nên làm

## Không push code lỗi

Trước khi push:

- Build thử
- Chạy test
- Kiểm tra syntax

---

## Không làm nhiều chức năng trong một branch

Sai:

```text
feature/login-dashboard-api
```

Đúng:

```text
feature/login
feature/dashboard
feature/api
```

---

## Không commit file rác

Ví dụ:

```text
__pycache__
venv
.env
```

Cần thêm `.gitignore`.

---


# 12. Các lệnh Git quan trọng

| Lệnh | Chức năng |
|---|---|
| git status | Kiểm tra trạng thái |
| git add . | Add file |
| git commit | Commit |
| git push | Push code |
| git pull | Lấy code mới |
| git checkout | Chuyển branch |
| git branch | Xem branch |
| git merge | Merge branch |
| git log | Xem lịch sử commit |
| git stash | Lưu thay đổi tạm thời |

---

# 13. Workflow tổng quát

```text
main
 ├── feature/login
 ├── feature/player-api
 ├── feature/socketio
 └── feature/dashboard-ui
```

Quy trình:

```text
1. Pull main
2. Tạo branch feature
3. Code
4. Commit
5. Push
6. Pull Request
7. Review
8. Merge vào main
```

# 15. Công cụ nên dùng

## Git GUI

- GitHub Desktop
- Sourcetree

---

## IDE

- VS Code
- PyCharm

---

# 16. Kết luận

Workflow tối giản và hiệu quả cho dự án 2 người:

```text
main
feature/*
```

Nguyên tắc quan trọng:

- Không code trực tiếp trên `main`
- Một feature = một branch
- Luôn pull trước khi code
- Review trước khi merge
- Commit rõ ràng
