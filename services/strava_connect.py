from sqlmodel import Session, select
from models.user_models import User, StravaAthlete
from models.stravaconnection import StravaConnection


def get_strava_connection(db: Session, athlete: StravaAthlete):
    connection_query = select(StravaConnection).where(
        StravaConnection.strava_user_id == athlete.id
    )

    connection = db.exec(connection_query).first()

    if connection:
        user = db.get(User, connection.user_skey)
        return user, connection

    user = User(
        firstname=athlete.firstname,
        lastname=athlete.lastname,
        city=athlete.city,
        state=athlete.state,
        country=athlete.country,
        sex=athlete.sex,
        created_via="strava"
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    strava_connection = StravaConnection(
        user_skey=user.user_skey,
        strava_user_id=athlete.id,
        created_at=athlete.created_at,
        updated_at=athlete.updated_at
    )

    db.add(strava_connection)
    db.commit()
    db.refresh(strava_connection)

    return user, strava_connection
