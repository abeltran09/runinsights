from sqlmodel import Session, select
from models.user_models import User, StravaAthlete


def create_user(db: Session, athlete: StravaAthlete):
    query = select(User).where(User.strava_user_id == athlete.id)
    existing_user = db.exec(query).first()

    if existing_user:
        return existing_user

    user = User(
            firstname=athlete.firstname,
            lastname=athlete.lastname,
            city=athlete.city,
            state=athlete.state,
            country=athlete.country,
            sex=athlete.sex
        )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user
