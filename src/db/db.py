import re
from typing import List
import logging as L
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker


from bands import Bands
from db.models.qsos import Qso
from db.models.activators import Activator, ActivatorSchema
from db.models.spot_comments import SpotComment, SpotCommentSchema
from db.models.spots import Spot, SpotSchema
from db.models.user_config import UserConfig, UserConfigSchema
from db.park_query import ParkQuery
from db.qso_query import QsoQuery
from db.loc_query import LocationQuery
from db.spot_query import SpotQuery
from utils.callsigns import get_basecall

Base = declarative_base()

logging = L.getLogger("db")
# show sql
# L.getLogger('sqlalchemy.engine').setLevel(L.INFO)


VER_FROM_ALEMBIC = 'd087ce5d50a6'
'''
This value indicates the version of the DB scheme the app is made for.

TODO: UPDATE THIS VERSION WHENEVER A ALEMBIC MIGRATION IS CREATED. This is
typically done by running `alembic revision` in the root of the project.
'''


class InitQuery:
    '''Internal DB queries stored here.'''

    def __init__(self, session: scoped_session):
        self.session = session

    def init_config(self):
        current = self.session.query(UserConfig).first()

        if current is None:
            cs = UserConfigSchema()
            logging.debug("creating default user config...")
            s = {'my_call': "W1AW",
                 'my_grid6': 'FN31pr',
                 'default_pwr': 1500,
                 'flr_host': "127.0.0.1",
                 'flr_port': 12345,
                 'adif_host': "127.0.0.1",
                 'adif_port': 12345}
            default_config = cs.load(s, session=self.session)
            self.session.add(default_config)
            self.session.commit()

    def init_alembic_ver(self):
        v = VER_FROM_ALEMBIC
        self.session.execute(sa.text('DROP TABLE IF EXISTS alembic_version;'))
        self.session.execute(sa.text('CREATE TABLE alembic_version(version_num varchar(32) NOT NULL);'))  # noqa E501
        self.session.execute(sa.text(f"INSERT INTO alembic_version(version_num) VALUES ('{v}');"))  # noqa E501
        self.session.commit()


class DataBase:
    def __init__(self):
        engine = sa.create_engine("sqlite:///spots.db", poolclass=sa.NullPool)
        self.session = scoped_session(sessionmaker(bind=engine))
        Base.metadata.create_all(engine)

        self._iq = InitQuery(self.session)
        self._lq = LocationQuery(self.session)
        self._qq = QsoQuery(self.session)
        self._pq = ParkQuery(self.session)
        self._sq = SpotQuery(self.session, func=self._get_all_filters)
        self._sq.delete_all_spots()
        self._iq.init_config()
        self._iq.init_alembic_ver()

        self.band_filter = Bands.NOBAND
        self.region_filter = None
        self.qrt_filter_on = True  # filter out QRT spots by default

    def commit_session(self):
        '''
        Calls session.commit to save any pending changes to db.

        May be required when for methods that use `delay_commit` param
        '''
        self.session.commit()

    '''
    These properties provide methods that were refactored from this class. If
    a method remains, we can assume its to integrated with other parts to be
    easily refactored.
    '''

    @property
    def qsos(self) -> QsoQuery:
        return self._qq

    @property
    def parks(self) -> ParkQuery:
        return self._pq

    @property
    def spots(self) -> SpotQuery:
        return self._sq

    @property
    def locations(self) -> LocationQuery:
        return self._lq

    def update_all_spots(self, spots_json):
        '''
        Updates all the spots in the database.

        First will delete all previous spots, read the ones passed in
        and perform the logic to update meta info about the spots

        :param dict spots_json: the dict from the pota api
        '''
        schema = SpotSchema()
        self.session.execute(sa.text('DELETE FROM spots;'))

        for s in spots_json:
            to_add: Spot = schema.load(s, session=self.session)
            self.session.add(to_add)

            # get meta data for this spot
            park = self.parks.get_park(to_add.reference)
            if park is not None and park.hunts > 0:
                to_add.park_hunts = park.hunts
            else:
                to_add.park_hunts = 0

            count = self.qsos.get_op_qso_count(to_add.activator)
            to_add.op_hunts = count

            hunted = self.qsos.get_spot_hunted_flag(
                to_add.activator, to_add.frequency, to_add.reference)
            bands = self.qsos.get_spot_hunted_bands(
                to_add.activator, to_add.reference)

            to_add.hunted = hunted
            to_add.hunted_bands = bands

            # if park is not None:
            #     loc_hunts = self._lq.get_location_hunts(park.locationDesc)
            #     to_add.loc_hunts = loc_hunts

            to_add.is_qrt = False

            if to_add.comments is not None:
                if re.match(r'\bqrt\b', to_add.comments.lower()):
                    to_add.is_qrt = True

        self.session.commit()

    def update_activator_stat(self, activator_stat_json) -> int:
        schema = ActivatorSchema()
        x = self.get_activator(activator_stat_json['callsign'])
        if x is None:
            to_add = schema.load(activator_stat_json, session=self.session)
            self.session.add(to_add)
            x = to_add
        else:
            # logging.debug(f"updating activator {x.activator_id}")
            schema.load(activator_stat_json, session=self.session, instance=x)

        self.session.commit()
        return x.activator_id

    def get_spot_comments(self, activator, park: str) -> List[SpotComment]:
        return self.session.query(SpotComment) \
            .filter(SpotComment.activator == activator,
                    SpotComment.park == park) \
            .order_by(SpotComment.spotTime.desc()) \
            .all()

    def get_activator(self, callsign: str) -> Activator:
        basecall = get_basecall(callsign)
        logging.debug(f"get_activator() basecall {basecall}")
        return self.session.query(Activator) \
            .filter(Activator.callsign == basecall) \
            .first()

    def get_activator_name(self, callsign: str) -> str:
        basecall = get_basecall(callsign)
        return self.session.query(Activator.name) \
            .filter(Activator.callsign == basecall) \
            .first()[0]

    def get_activator_by_id(self, id: int) -> Activator:
        return self.session.query(Activator).get(id)

    def get_user_config(self) -> UserConfig:
        return self.session.query(UserConfig).first()

    def get_version(self) -> str:
        sql = 'SELECT version_num FROM alembic_version'
        v = self.session.execute(sa.text(sql))
        return v.fetchone()[0]

    def insert_spot_comments(self,
                             activator: str,
                             park: str,
                             comments: any):
        sql = sa.text(f"DELETE FROM comments WHERE activator='{activator}' AND park='{park}' ;")  # noqa E501
        self.session.execute(sql)
        self.session.commit()

        if comments is None:
            return

        for x in comments:
            x["activator"] = activator
            x["park"] = park

        # logging.debug(f"inserting {comments}")
        ss = SpotCommentSchema(many=True)
        to_add = ss.load(comments, session=self.session)
        self.session.add_all(to_add)
        self.session.commit()

    def update_user_config(self, json: any):
        schema = UserConfigSchema()
        config = self.get_user_config()
        schema.load(json, session=self.session, instance=config)
        self.session.commit()

    def build_qso_from_spot(self, spot_id: int) -> Qso:
        '''
        Builds a new `Qso` with data in the spot table.

        Also uses data from Activators table.

        :param int spot_id: the spot PK.
        :returns an untracked `Qso` object with initialized data.
        '''
        s = self.spots.get_spot(spot_id)
        if (s is None):
            q = Qso()
            q.comment = "Error no spot"
            return q
        a = self.get_activator(s.activator)
        if s is not None:
            q = Qso()
            q.init_from_spot(s, a.name)
            return q

    def set_band_filter(self, band: Bands):
        logging.debug(f"db setting band filter to {band}")
        self.band_filter = band

    def set_region_filter(self, region: str):
        logging.debug(f"db setting region filter to {region}")
        self.region_filter = region

    def set_qrt_filter(self, is_on: bool):
        logging.debug(f"db setting QRT filter to {is_on}")
        self.qrt_filter_on = is_on

    def _get_all_filters(self) -> list[sa.ColumnElement[bool]]:
        return self._get_band_filters() + \
            self._get_region_filters() + \
            self._get_qrt_filter()

    def _get_band_filters(self) -> list[sa.ColumnElement[bool]]:
        band = Bands(self.band_filter)  # not sure why cast is needed
        if band == Bands.NOBAND:
            return []
        terms = QsoQuery.get_band_lmt_terms(band, Spot.frequency)
        return terms

    def _get_region_filters(self) -> list[sa.ColumnElement[bool]]:
        region = self.region_filter
        if (region is None):
            return []
        terms = [Spot.locationDesc.startswith(region)]
        return terms

    def _get_qrt_filter(self) -> list[sa.ColumnElement[bool]]:
        qrt = self.qrt_filter_on
        if qrt:
            return [Spot.is_qrt == False]  # noqa E712
        terms = []
        return terms
