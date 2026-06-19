from datetime import date, datetime, timedelta
from database import SessionLocal, Base, engine
from models import Clinic, Doctor, Patient, CleaningRecord, Followup, Appointment, Alert


def init_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        clinics = [
            Clinic(name="阳光口腔-朝阳门店", store_manager="张经理", manager_phone="13800000001"),
            Clinic(name="阳光口腔-海淀店", store_manager="李经理", manager_phone="13800000002"),
            Clinic(name="阳光口腔-西城店", store_manager="王经理", manager_phone="13800000003"),
        ]
        db.add_all(clinics)
        db.flush()

        doctors = [
            Doctor(clinic_id=clinics[0].id, name="陈医生", title="主治医师", phone="13900000001"),
            Doctor(clinic_id=clinics[0].id, name="刘医生", title="副主任医师", phone="13900000002"),
            Doctor(clinic_id=clinics[1].id, name="赵医生", title="主治医师", phone="13900000003"),
            Doctor(clinic_id=clinics[1].id, name="孙医生", title="医师", phone="13900000004"),
            Doctor(clinic_id=clinics[2].id, name="周医生", title="主治医师", phone="13900000005"),
        ]
        db.add_all(doctors)
        db.flush()

        patients_data = [
            ("王小明", "13611110001", "常规洁治"),
            ("李美丽", "13611110002", "种植"),
            ("张三峰", "13611110003", "正畸"),
            ("刘小华", "13611110004", "牙周维护"),
            ("陈大伟", "13611110005", "常规洁治"),
            ("赵雅婷", "13611110006", "种植"),
            ("孙志强", "13611110007", "常规洁治"),
            ("周美玲", "13611110008", "正畸"),
            ("吴国庆", "13611110009", "牙周维护"),
            ("郑丽娜", "13611110010", "常规洁治"),
            ("冯建国", "13611110011", "种植"),
            ("黄晓燕", "13611110012", "常规洁治"),
        ]
        patients = []
        for name, phone, ptype in patients_data:
            p = Patient(name=name, phone=phone, patient_type=ptype)
            db.add(p)
            db.flush()
            patients.append(p)

        today = date.today()
        cleaning_data = [
            (clinics[0].id, doctors[0].id, patients[0].id, today - timedelta(days=5), "常规超声波洁治"),
            (clinics[0].id, doctors[0].id, patients[1].id, today - timedelta(days=35), "种植体维护洁治"),
            (clinics[0].id, doctors[1].id, patients[2].id, today - timedelta(days=25), "正畸期间洁治"),
            (clinics[0].id, doctors[1].id, patients[3].id, today - timedelta(days=15), "牙周深层洁治"),
            (clinics[0].id, doctors[0].id, patients[4].id, today - timedelta(days=2), "常规洁治"),
            (clinics[1].id, doctors[2].id, patients[5].id, today - timedelta(days=40), "种植维护洁治"),
            (clinics[1].id, doctors[2].id, patients[6].id, today - timedelta(days=4), "常规洁治"),
            (clinics[1].id, doctors[3].id, patients[7].id, today - timedelta(days=22), "正畸清洁"),
            (clinics[1].id, doctors[3].id, patients[8].id, today - timedelta(days=8), "牙周维护"),
            (clinics[2].id, doctors[4].id, patients[9].id, today - timedelta(days=6), "常规洁治"),
            (clinics[2].id, doctors[4].id, patients[10].id, today - timedelta(days=32), "种植洁治"),
            (clinics[2].id, doctors[4].id, patients[11].id, today - timedelta(days=1), "常规洁治"),
        ]
        cleaning_records = []
        for cid, did, pid, cdate, notes in cleaning_data:
            rec = CleaningRecord(
                clinic_id=cid, doctor_id=did, patient_id=pid,
                cleaning_date=cdate, notes=notes
            )
            db.add(rec)
            db.flush()
            cleaning_records.append(rec)

        followups_data = [
            (cleaning_records[1].id, patients[1].id, today - timedelta(days=33, hours=-10),
             "客服小王", "电话", "患者感觉良好，无不适", False, False, False, None, "半年后复查"),
            (cleaning_records[2].id, patients[2].id, today - timedelta(days=23, hours=-9),
             "客服小李", "微信", "患者反馈轻微敏感，已建议使用脱敏牙膏", False, True, False, None, "1个月后复诊"),
            (cleaning_records[4].id, patients[4].id, today - timedelta(days=1, hours=-8),
             "客服小王", "电话", "患者无异常", False, False, False, None, "定期检查"),
            (cleaning_records[6].id, patients[6].id, today - timedelta(days=3, hours=-14),
             "客服小张", "电话", "患者反馈仍有牙龈出血，建议复查", True, False, False, None, "安排复查"),
            (cleaning_records[7].id, patients[7].id, today - timedelta(days=20, hours=-10),
             "客服小张", "微信", "患者情况良好", False, False, False, None, "3周后复诊"),
            (cleaning_records[8].id, patients[8].id, today - timedelta(days=6, hours=-11),
             "客服小李", "电话", "患者反馈牙龈肿痛、出血", True, False, True, "咬合不适", "尽快复诊"),
            (cleaning_records[10].id, patients[10].id, today - timedelta(days=30, hours=-9),
             "客服小王", "电话", "患者反馈尚可", False, False, False, None, "1个月后复诊"),
            (cleaning_records[11].id, patients[11].id, today - timedelta(days=0, hours=-2),
             "客服小李", "短信", "已发送关怀短信", False, False, False, None, "1周后回访"),
        ]
        for rid, pid, ftime, op, method, feedback, bleed, sens, pain, other, nstep in followups_data:
            f = Followup(
                cleaning_record_id=rid, patient_id=pid, followup_time=ftime,
                operator=op, contact_method=method, patient_feedback=feedback,
                has_bleeding=bleed, has_sensitivity=sens, has_pain=pain,
                other_symptoms=other, next_step=nstep
            )
            db.add(f)

        appointments_data = [
            (cleaning_records[1].id, patients[1].id, today + timedelta(days=150), "种植复查", "待就诊"),
            (cleaning_records[2].id, patients[2].id, today + timedelta(days=7), "正畸调整", "待就诊"),
            (cleaning_records[4].id, patients[4].id, today + timedelta(days=180), "常规检查", "待就诊"),
            (cleaning_records[7].id, patients[7].id, today + timedelta(days=5), "正畸复诊", "待就诊"),
            (cleaning_records[10].id, patients[10].id, today - timedelta(days=2), "种植复查", "已就诊"),
        ]
        for rid, pid, adate, atype, status in appointments_data:
            a = Appointment(
                cleaning_record_id=rid, patient_id=pid,
                appointment_date=adate, appointment_type=atype, status=status
            )
            db.add(a)

        db.commit()
        print("示例数据初始化完成！")
        print(f"门店: {len(clinics)} 家")
        print(f"医生: {len(doctors)} 位")
        print(f"患者: {len(patients)} 位")
        print(f"洁治记录: {len(cleaning_records)} 条")
        print(f"随访记录: {len(followups_data)} 条")
        print(f"预约记录: {len(appointments_data)} 条")

    finally:
        db.close()


if __name__ == "__main__":
    init_db()
