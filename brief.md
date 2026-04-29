Software Requirements Specification (SRS)
ระบบจองห้องประชุมและห้องเรียน
ภาควิชาวิศวกรรมไฟฟ้าและคอมพิวเตอร์
Version: 1.0
วันที่: 7 เมษายน 2569
แพลตฟอร์ม: Django Web Application

1. บทนำ (Introduction)
1.1 วัตถุประสงค์ (Purpose)
เอกสารฉบับนี้กำหนดข้อกำหนดความต้องการซอฟต์แวร์ (Software Requirements Specification) สำหรับระบบจองห้องประชุมและห้องเรียนของภาควิชาวิศวกรรมไฟฟ้าและคอมพิวเตอร์ 

1.2 ขอบเขตของระบบ (Scope)
ระบบนี้เป็น Web Application พัฒนาด้วย Django Framework สำหรับการจองห้องประชุมและห้องเรียนจำนวน 5 ห้อง ภายในภาควิชา โดยรองรับการยืนยันตัวตนผ่าน TU REST API, การแสดงปฏิทินห้องว่าง, ระบบอนุมัติการจอง, การแจ้งเตือนผ่าน Email และรายงานสถิติการใช้ห้อง

1.3 คำจำกัดความ (Definitions)
คำศัพท์	ความหมาย
ผู้จอง (Booker)	อาจารย์ในภาควิชาที่ต้องการจองห้อง
ผู้ดูแลระบบ (Admin)	เจ้าหน้าที่ภาควิชาที่ทำหน้าที่อนุมัติและจัดการการจอง
TU REST API	ระบบยืนยันตัวตนของมหาวิทยาลัยธรรมศาสตร์
Booking	รายการจองห้องที่สร้างโดยผู้จอง
Approval	กระบวนการอนุมัติการจองโดย Admin
1.4 เอกสารอ้างอิง (References)
TU REST API Documentation: https://restapi.tu.ac.th/api/v1/auth/Ad/verify

2. ภาพรวมของระบบ (System Overview)
2.1 บริบทของระบบ (System Context)
ระบบจองห้องประชุมเชื่อมต่อกับระบบภายนอก 2 ส่วน:

TU REST API — สำหรับยืนยันตัวตนผู้ใช้ (Authentication)

Email Server (SMTP) — สำหรับส่งอีเมลแจ้งเตือนและยืนยันการจอง 

2.2 ผู้ใช้งาน (User Roles)
Role	คำอธิบาย	สิทธิ์หลัก
อาจารย์ (Lecturer)	อาจารย์ในภาควิชาฯ	จอง, ดูปฏิทิน, ยกเลิกการจองตนเอง
เจ้าหน้าที่ (Admin)	เจ้าหน้าที่ภาควิชาฯ	อนุมัติ/ปฏิเสธ, จัดการห้อง, ดูรายงาน, จัดการผู้ใช้
2.3 ข้อมูลห้อง (Room Information)
รหัสห้อง	ชื่อห้อง	ประเภท	จำนวนที่นั่ง
406-3	ห้องประชุม 1	ห้องประชุม	60
406-5	ห้องประชุม 2	ห้องประชุม	15
408-1	ห้องประชุม 3	ห้องประชุม	10
408-2/1	ห้องบรรยาย 1	ห้องเรียน	20
408-2/2	ห้องบรรยาย 2	ห้องเรียน	20
3. ข้อกำหนดเชิงหน้าที่ (Functional Requirements)
3.1 โมดูลยืนยันตัวตน (Authentication Module)
ID	ข้อกำหนด	ลำดับความสำคัญ
FR-AUTH-01	ระบบต้องรองรับการ Login ผ่าน TU REST API โดยใช้ Username/Password ของมหาวิทยาลัย	Must
FR-AUTH-02	ระบบต้องส่ง POST request ไปที่ https://restapi.tu.ac.th/api/v1/auth/Ad/verify พร้อม Application-Key, UserName, PassWord	Must
FR-AUTH-03	ระบบต้องจัดเก็บ Session หลัง Login สำเร็จ เพื่อไม่ต้อง Login ซ้ำทุกครั้ง	Must
FR-AUTH-04	ระบบต้องรองรับ Logout และทำลาย Session	Must
FR-AUTH-05	ระบบต้องกำหนด Role (Lecturer / Admin) ให้ผู้ใช้หลัง Login ครั้งแรก โดย Admin เป็นผู้กำหนด	Must
3.2 โมดูลจองห้อง (Booking Module)
ID	ข้อกำหนด	ลำดับความสำคัญ
FR-BOOK-01	ผู้จองต้องเลือกห้องที่ต้องการจากรายการห้องทั้ง 5 ห้อง	Must
FR-BOOK-02	ผู้จองต้องระบุวัตถุประสงค์การใช้งาน โดยเลือกจาก 2 ประเภท: (ก) สอนปกติ/ชดเชย/เสริม — ต้องระบุรหัสและชื่อวิชา พร้อมเลือกหลักสูตร (ปริญญาตรีภาคปกติ / ปริญญาโท / TEP-TEPE / TU-PINE) หรือ (ข) จัดอบรม/จัดติว — ต้องระบุชื่อเรื่อง	Must
FR-BOOK-03	ผู้จองต้องระบุช่วงวันที่ใช้งาน (วันเริ่มต้น — วันสิ้นสุด)	Must
FR-BOOK-04	ผู้จองต้องเลือกวันในสัปดาห์ที่ใช้งาน (จันทร์–ศุกร์ เลือกได้หลายวัน หรือเลือก "ทุกวัน")	Must
FR-BOOK-05	ผู้จองต้องระบุเวลาเริ่มต้นและสิ้นสุดการใช้งาน	Must
FR-BOOK-06	ระบบต้องตรวจสอบความซ้ำซ้อนของการจอง (Conflict Detection) ก่อนบันทึก ถ้าห้องถูกจองในช่วงเวลาเดียวกันแล้ว ต้องแจ้งเตือนผู้จอง	Must
FR-BOOK-07	ระบบต้องบันทึกชื่อผู้จองอัตโนมัติจากข้อมูล Login	Must
FR-BOOK-08	ผู้จองสามารถดูรายการจองของตนเอง และยกเลิกการจองที่ยังไม่ถึงวันใช้งานได้	Should
FR-BOOK-09	ระบบต้องรองรับการจองแบบซ้ำ (Recurring) ตาม pattern วันที่เลือก เช่น ทุกวันอังคารและพฤหัสบดี ตั้งแต่วันที่ X ถึง Y	Should
3.3 โมดูลอนุมัติ (Approval Module)
ID	ข้อกำหนด	ลำดับความสำคัญ
FR-APPR-01	การจองทุกรายการต้องผ่านการอนุมัติจาก Admin ก่อนจึงจะสมบูรณ์ (ตามเงื่อนไขเดิมในแบบฟอร์ม)	Must
FR-APPR-02	Admin ต้องสามารถดูรายการจองที่รอการอนุมัติทั้งหมด	Must
FR-APPR-03	Admin ต้องสามารถ "อนุมัติ" หรือ "ปฏิเสธ" การจองแต่ละรายการ พร้อมระบุเหตุผลกรณีปฏิเสธ	Must
FR-APPR-04	ระบบต้องส่ง Email แจ้งผู้จองเมื่อสถานะการจองเปลี่ยน (อนุมัติ/ปฏิเสธ)	Must
3.4 โมดูลปฏิทิน (Calendar Module)
ID	ข้อกำหนด	ลำดับความสำคัญ
FR-CAL-01	ระบบต้องแสดงปฏิทินตารางห้องว่าง (Calendar View) แบบรายสัปดาห์และรายเดือน	Must
FR-CAL-02	ผู้ใช้ต้องสามารถกรองปฏิทินตามห้องที่ต้องการดูได้	Must
FR-CAL-03	ปฏิทินต้องแสดงสถานะการจองด้วยสี: ว่าง, รอการอนุมัติ (Pending), อนุมัติแล้ว (Approved)	Should
FR-CAL-04	ผู้ใช้สามารถคลิกที่ช่วงเวลาว่างบนปฏิทินเพื่อเริ่มการจองได้	Could
3.5 โมดูลแจ้งเตือน (Notification Module)
ID	ข้อกำหนด	ลำดับความสำคัญ
FR-NOTI-01	ระบบต้องส่ง Email แจ้ง Admin เมื่อมีการจองใหม่เข้ามา	Must
FR-NOTI-02	ระบบต้องส่ง Email แจ้งผู้จองเมื่อการจองได้รับการอนุมัติหรือถูกปฏิเสธ	Must
FR-NOTI-03	ระบบควรส่ง Email เตือนผู้จองล่วงหน้า 1 วันก่อนวันใช้งาน	Could
3.6 โมดูลรายงาน (Report Module)
ID	ข้อกำหนด	ลำดับความสำคัญ
FR-RPT-01	Admin ต้องสามารถดูรายงานสถิติการใช้ห้องแต่ละห้อง (จำนวนครั้ง, ชั่วโมง) ในช่วงเวลาที่กำหนด	Must
FR-RPT-02	Admin ต้องสามารถดูรายงานอัตราการใช้งานห้อง (Utilization Rate)	Should
FR-RPT-03	Admin ควรสามารถ Export รายงานเป็น CSV หรือ Excel	Could
FR-RPT-04	รายงานควรแสดงสถิติแยกตามประเภทการใช้งาน (สอน/อบรม) และตามหลักสูตร	Could
3.7 โมดูลจัดการระบบ (Administration Module)
ID	ข้อกำหนด	ลำดับความสำคัญ
FR-ADM-01	Admin ต้องสามารถเพิ่ม แก้ไข หรือปิดการใช้งานห้องในระบบ	Should
FR-ADM-02	Admin ต้องสามารถกำหนด Role ของผู้ใช้ (Lecturer / Admin)	Must
FR-ADM-03	Admin ควรสามารถกำหนดช่วงเวลาที่ห้องไม่พร้อมใช้งาน (Blackout Period) เช่น ช่วงปิดเทอม	Could
4. ข้อกำหนดเชิงไม่ใช่หน้าที่ (Non-Functional Requirements)
4.1 ความปลอดภัย (Security)
ID	ข้อกำหนด
NFR-SEC-01	ข้อมูลรหัสผ่านต้องไม่ถูกจัดเก็บในระบบ — ใช้ TU REST API ยืนยันทุกครั้ง
NFR-SEC-02	การสื่อสารระหว่าง Client-Server ต้องใช้ HTTPS
NFR-SEC-03	Session ต้องมี timeout ที่เหมาะสม (เช่น 8 ชั่วโมง)
NFR-SEC-04	ระบบต้องป้องกัน CSRF, SQL Injection และ XSS (ใช้ Django built-in protection)
4.2 ความสามารถในการใช้งาน (Usability)
ID	ข้อกำหนด
NFR-USE-01	ส่วนต่อประสานผู้ใช้ (UI) ต้องเป็นภาษาไทย
NFR-USE-02	ระบบต้องรองรับการใช้งานบน Desktop Browser และ Mobile Browser (Responsive Design)
NFR-USE-03	ผู้ใช้ใหม่ต้องสามารถทำการจองสำเร็จได้ภายใน 3 นาทีโดยไม่ต้องอ่านคู่มือ
4.3 ข้อจำกัดทางเทคนิค (Technical Constraints)
ID	ข้อกำหนด
NFR-TECH-01	พัฒนาด้วย Django Framework (Python)
NFR-TECH-02	ใช้ฐานข้อมูล PostgreSQL หรือ SQLite (สำหรับช่วงพัฒนา)
NFR-TECH-03	Authentication ผ่าน TU REST API ตาม endpoint ที่กำหนด
NFR-TECH-04	ใช้ Django Template หรือ Django REST Framework + Frontend (ตามการออกแบบ)
NFR-TECH-05	ระบบต้องรัน Deploy ด้วย Docker ตาม Docker image ที่อาจารย์กำหนดให้
NFR-TECH-06	ต้องมีการใช้งาน CSS Grid ร่วมกับ Django Template
5. Use Cases สรุป
UC-01: Login เข้าสู่ระบบ
Actor: Lecturer, Admin

Precondition: มีบัญชี TU Account

Flow: ผู้ใช้กรอก Username/Password → ระบบส่งไปยัง TU REST API → ยืนยันสำเร็จ → สร้าง Session → Redirect ไปหน้า Dashboard

Alternative: ยืนยันไม่สำเร็จ → แสดงข้อความผิดพลาด

UC-02: จองห้อง
Actor: Lecturer

Precondition: Login แล้ว

Flow: เลือกห้อง → กรอกวัตถุประสงค์ → กำหนดวันเวลา → ระบบตรวจสอบ Conflict → บันทึก (สถานะ Pending) → ส่ง Email แจ้ง Admin

Alternative: ตรวจพบ Conflict → แจ้งเตือน → ให้เลือกวันเวลาใหม่

UC-03: อนุมัติ/ปฏิเสธการจอง
Actor: Admin

Precondition: มีการจอง Pending อยู่ในระบบ

Flow: Admin เข้าดูรายการ Pending → เลือกอนุมัติหรือปฏิเสธ (พร้อมเหตุผล) → ระบบอัปเดตสถานะ → ส่ง Email แจ้งผู้จอง

UC-04: ดูปฏิทินห้องว่าง
Actor: Lecturer, Admin

Precondition: Login แล้ว

Flow: เลือกห้อง → ระบบแสดงปฏิทินรายสัปดาห์/รายเดือน → แสดงสถานะ Booking แต่ละช่วงเวลา

UC-05: ดูรายงานสถิติ
Actor: Admin

Precondition: Login แล้ว, มี Role เป็น Admin

Flow: เลือกช่วงเวลา → ระบบแสดงสถิติการใช้ห้อง, อัตราการใช้งาน, แยกตามประเภท

UC-06: ยกเลิกการจอง
Actor: Lecturer

Precondition: มี Booking ที่ยังไม่ถึงวันใช้งาน

Flow: เลือก Booking → กดยกเลิก → ระบบอัปเดตสถานะ → ส่ง Email แจ้ง Admin

6. MoSCoW Priority Summary
Priority	จำนวน Requirements	ตัวอย่าง
Must	18	Login, จอง, อนุมัติ, ปฏิทิน, Conflict Detection, Email แจ้งเตือน
Should	6	Recurring Booking, ดูรายการจองตนเอง, Utilization Rate, จัดการห้อง
Could	6	คลิกปฏิทินเพื่อจอง, Email เตือนล่วงหน้า, Export รายงาน, Blackout Period
7. สมมติฐานและข้อจำกัด (Assumptions & Constraints)
สมมติฐาน
ผู้ใช้ทุกคนมีบัญชี TU Account ที่สามารถยืนยันผ่าน TU REST API ได้

การแจ้งเตือนให้ใช้อีเมล @gmail.com ในการแจ้งเตือนในระหว่างพัฒนาระบบ (สร้างอีเมลใหม่สำหรับระบบใช้งานกับระบบนี้)

Application-Key สำหรับ TU REST API ให้สมัครใช้งานจาก https://restapi.tu.ac.th

ห้องทั้ง 5 ห้องเป็นข้อมูลเริ่มต้น แต่ Admin สามารถเพิ่ม/แก้ไขภายหลังได้

ข้อจำกัด
ระบบรองรับเฉพาะบุคลากรภายในภาควิชาเท่านั้น (ไม่เปิดให้ภายนอก)

ไม่มีระบบชำระเงินค่าห้อง

ภาคผนวก: TU REST API Reference
Endpoint: POST https://restapi.tu.ac.th/api/v1/auth/Ad/verify
Headers:
  Content-Type: application/json
  Application-Key: {Access Token}
Body:
  {
    "UserName": "{username}",
    "PassWord": "{password}"
  }