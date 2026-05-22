# ชื่อโปรเจกต์ - Roommasat - CN334

## ข้อมูลกลุ่ม

| บทบาท | รหัสนักศึกษา | ชื่อ-สกุล |
|-------|------------|-----------------------|
| หัวหน้า | 6610685239 | นายปรัญชัย ติ้มขลิบ       |
| สมาชิก | 6610685056 | นายชนม์ชนันทร์ จิตระวัง    |
| สมาชิก | 6610685098 | นายกฤติเดช วิชัยดิษฐ      |
| สมาชิก | 6610685122 | นายชยวัฒน์ กาญจนะแก้ว   |
| สมาชิก | 6610685205 | นายนนทพัทธ์ บุญประสิทธิ์   |

## การแบ่งหน้าที่

| รหัสนักศึกษา | ความรับผิดชอบ |
|---|---|
| 6610685239 | ระบบ bookings, email notification, calendar, database, fixtures|
| 6610685056 | admin dashboard , admin report, รายงาน |
| 6610685098 | bug fix, tester, merge branch|
| 6610685122 | dashboard , ระบบ line chatbot  |
| 6610685205 | templates, CSS, frontend, responsive design |

## สิ่งที่ต้องติดตั้งก่อนรันโปรเจกต์

- ติดตั้ง Docker Desktop และเปิดใช้งานอยู่
- Port 8000 ต้องว่างอยู่

## วิธีรันโปรเจกต์

```bash
# 1. เริ่มต้น containers
docker compose up --build

# 2. เปิด terminal ใหม่ แล้วรัน migrations
docker compose exec web python manage.py migrate

# 3. โหลดข้อมูลตัวอย่าง
docker compose exec web python manage.py loaddata fixtures/initial_data.json

# 4. สร้าง superuser (ถ้าจำเป็น)
docker compose exec web python manage.py createsuperuser

# 5. เปิดในเบราว์เซอร์
http://localhost:8000
```

## บัญชีสำหรับทดสอบ
 | บทบาท | Username | Password |
|-----------|----------|-----------|
| Admin | admin | admin |
| ผู้ใช้งาน | testuser | password123 |
