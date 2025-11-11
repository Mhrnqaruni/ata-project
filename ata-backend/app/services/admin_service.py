# /ata-backend/app/services/admin_service.py

"""
Admin service to fetch comprehensive database statistics and data.
"""

from typing import Dict, List, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models.user_model import User
from app.db.models.class_student_models import Class, Student, StudentClassMembership
from app.db.models.assessment_models import Assessment, Result
from app.db.models.outsider_student import OutsiderStudent
from app.db.models.chat_models import ChatSession, ChatMessage
from app.db.models.generation_models import Generation
from app.db.models.ai_model_run import AIModelRun


def get_admin_dashboard_data(db: Session) -> Dict[str, Any]:
    """
    Fetches comprehensive statistics and data from the entire database.

    Returns:
        Dictionary containing all database statistics and detailed data
    """

    # ==================== SUMMARY STATISTICS ====================
    total_users = db.query(func.count(User.id)).scalar()
    total_classes = db.query(func.count(Class.id)).scalar()
    total_students = db.query(func.count(Student.id)).scalar()
    total_assessments = db.query(func.count(Assessment.id)).scalar()
    total_results = db.query(func.count(Result.id)).scalar()
    total_outsider_students = db.query(func.count(OutsiderStudent.id)).scalar()
    total_chat_sessions = db.query(func.count(ChatSession.id)).scalar()
    total_chat_messages = db.query(func.count(ChatMessage.id)).scalar()
    total_generations = db.query(func.count(Generation.id)).scalar()
    total_ai_runs = db.query(func.count(AIModelRun.id)).scalar()
    total_memberships = db.query(func.count(StudentClassMembership.id)).scalar()

    # ==================== USERS DATA ====================
    users = db.query(User).all()
    users_data = []
    for user in users:
        user_classes_count = db.query(func.count(Class.id)).filter(Class.user_id == user.id).scalar()
        user_assessments_count = db.query(func.count(Assessment.id)).filter(Assessment.user_id == user.id).scalar()
        user_chat_sessions_count = db.query(func.count(ChatSession.id)).filter(ChatSession.user_id == user.id).scalar()
        user_generations_count = db.query(func.count(Generation.id)).filter(Generation.user_id == user.id).scalar()

        users_data.append({
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "classes_count": user_classes_count,
            "assessments_count": user_assessments_count,
            "chat_sessions_count": user_chat_sessions_count,
            "generations_count": user_generations_count
        })

    # ==================== CLASSES DATA ====================
    classes = db.query(Class).all()
    classes_data = []
    for cls in classes:
        student_count = db.query(func.count(StudentClassMembership.id)).filter(
            StudentClassMembership.class_id == cls.id
        ).scalar()

        owner = db.query(User).filter(User.id == cls.user_id).first()

        classes_data.append({
            "id": cls.id,
            "name": cls.name,
            "description": cls.description,
            "owner_email": owner.email if owner else "Unknown",
            "student_count": student_count
        })

    # ==================== STUDENTS DATA ====================
    students = db.query(Student).all()
    students_data = []
    for student in students:
        classes_count = db.query(func.count(StudentClassMembership.id)).filter(
            StudentClassMembership.student_id == student.id
        ).scalar()

        classes_list = db.query(Class.name).join(
            StudentClassMembership,
            StudentClassMembership.class_id == Class.id
        ).filter(StudentClassMembership.student_id == student.id).all()

        students_data.append({
            "id": student.id,
            "name": student.name,
            "studentId": student.studentId,
            "overallGrade": student.overallGrade,
            "classes_count": classes_count,
            "classes": [cls.name for cls in classes_list]
        })

    # ==================== ASSESSMENTS DATA ====================
    assessments = db.query(Assessment).all()
    assessments_data = []
    for assessment in assessments:
        results_count = db.query(func.count(Result.id)).filter(Result.job_id == assessment.id).scalar()
        owner = db.query(User).filter(User.id == assessment.user_id).first()

        assessments_data.append({
            "id": assessment.id,
            "status": assessment.status,
            "created_at": assessment.created_at.isoformat() if assessment.created_at else None,
            "owner_email": owner.email if owner else "Unknown",
            "total_pages": assessment.total_pages,
            "results_count": results_count,
            "config": assessment.config
        })

    # ==================== RESULTS DATA ====================
    results = db.query(Result).limit(100).all()  # Limit to first 100 for performance
    results_data = []
    for result in results:
        student_name = None
        if result.student_id:
            student = db.query(Student).filter(Student.id == result.student_id).first()
            student_name = student.name if student else "Unknown"
        elif result.outsider_student_id:
            outsider = db.query(OutsiderStudent).filter(OutsiderStudent.id == result.outsider_student_id).first()
            student_name = outsider.name if outsider else "Unknown"

        results_data.append({
            "id": result.id,
            "job_id": result.job_id,
            "student_name": student_name,
            "question_id": result.question_id,
            "grade": result.grade,
            "status": result.status,
            "finalized_by": result.finalized_by.value if result.finalized_by else None
        })

    # ==================== OUTSIDER STUDENTS DATA ====================
    outsider_students = db.query(OutsiderStudent).all()
    outsider_students_data = []
    for outsider in outsider_students:
        results_count = db.query(func.count(Result.id)).filter(Result.outsider_student_id == outsider.id).scalar()

        outsider_students_data.append({
            "id": outsider.id,
            "name": outsider.name,
            "job_id": outsider.assessment_id,
            "results_count": results_count
        })

    # ==================== CHAT SESSIONS DATA ====================
    chat_sessions = db.query(ChatSession).all()
    chat_sessions_data = []
    for session in chat_sessions:
        messages_count = db.query(func.count(ChatMessage.id)).filter(ChatMessage.session_id == session.id).scalar()
        owner = db.query(User).filter(User.id == session.user_id).first()

        chat_sessions_data.append({
            "id": session.id,
            "title": session.name,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "owner_email": owner.email if owner else "Unknown",
            "messages_count": messages_count
        })

    # ==================== GENERATIONS DATA ====================
    generations = db.query(Generation).all()
    generations_data = []
    for gen in generations:
        owner = db.query(User).filter(User.id == gen.user_id).first()

        generations_data.append({
            "id": gen.id,
            "tool_type": gen.tool_id,
            "created_at": gen.created_at.isoformat() if gen.created_at else None,
            "owner_email": owner.email if owner else "Unknown"
        })

    # ==================== AI MODEL RUNS DATA ====================
    ai_runs = db.query(AIModelRun).all()
    ai_runs_data = []
    for run in ai_runs:
        ai_runs_data.append({
            "id": str(run.id),
            "job_id": run.job_id,
            "question_id": run.question_id,
            "run_index": run.run_index,
            "grade": float(run.grade) if run.grade else None,
            "created_at": run.created_at.isoformat() if run.created_at else None
        })

    # AI cost and token tracking not available in current schema
    total_ai_cost = 0.0
    total_ai_tokens = 0

    # ==================== BUILD RESPONSE ====================
    return {
        "summary": {
            "total_users": total_users,
            "total_classes": total_classes,
            "total_students": total_students,
            "total_assessments": total_assessments,
            "total_results": total_results,
            "total_outsider_students": total_outsider_students,
            "total_chat_sessions": total_chat_sessions,
            "total_chat_messages": total_chat_messages,
            "total_generations": total_generations,
            "total_ai_runs": total_ai_runs,
            "total_memberships": total_memberships,
            "total_ai_cost": round(total_ai_cost, 4),
            "total_ai_tokens": total_ai_tokens
        },
        "users": users_data,
        "classes": classes_data,
        "students": students_data,
        "assessments": assessments_data,
        "results": results_data,
        "outsider_students": outsider_students_data,
        "chat_sessions": chat_sessions_data,
        "generations": generations_data,
        "ai_runs": ai_runs_data
    }
