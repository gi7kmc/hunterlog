from datetime import datetime
import re
from typing import List
import logging as L
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker


from bands import bandLimits, bandNames, Bands, get_band
from db.models.qsos import Qso
from db.models.activators import Activator, ActivatorSchema
from db.models.spot_comments import SpotComment, SpotCommentSchema
from db.models.spots import Spot, SpotSchema
from db.models.user_config import UserConfig, UserConfigSchema
from db.models.parks import Park, ParkSchema
from utils.callsigns import get_basecall

Base = declarative_base()

logging = L.getLogger("db")
# show sql
# L.getLogger('sqlalchemy.engine').setLevel(L.INFO)


VER_FROM_ALEMBIC = 'de225609f3b5'
'''
This value indicates the version of the DB scheme the app is made for.

TODO: UPDATE THIS VERSION WHENEVER A ALEMBIC MIGRATION IS CREATED. This is
typically done by running `alembic revision` in the root of the project.
'''


class DataBase:
    def __init__(self):
        engine = sa.create_engine("sqlite:///spots.db", poolclass=sa.NullPool)
        self.session = scoped_session(sessionmaker(bind=engine))
        Base.metadata.create_all(engine)

        self.session.execute(sa.text('DELETE FROM spots;'))
        self.session.commit()
        self.init_config()
        self.band_filter = Bands.NOBAND
        self.region_filter = None
        self.qrt_filter_on = True  # filter out QRT spots by default

        self._init_alembic_ver()

    def commit_session(self):
        '''
        Calls session.commit to save any pending changes to db.
        '''
        self.session.commit()

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

    def update_all_spots(self, spots_json):
        schema = SpotSchema()

        self.session.execute(sa.text('DELETE FROM spots;'))
        for s in spots_json:
            to_add: Spot = schema.load(s, session=self.session)
            self.session.add(to_add)

            # get meta data for this spot
            park = self.get_park(to_add.reference)
            if park is not None and park.hunts > 0:
                to_add.park_hunts = park.hunts
            else:
                to_add.park_hunts = 0

            count = self.get_op_qso_count(to_add.activator)
            to_add.op_hunts = count

            hunted = self.get_spot_hunted_flag(
                to_add.activator, to_add.frequency, to_add.reference)
            bands = self.get_spot_hunted_bands(
                to_add.activator, to_add.reference)

            to_add.hunted = hunted
            to_add.hunted_bands = bands

            to_add.is_qrt = False

            if to_add.comments is not None:
                if re.match(r'\bqrt\b', to_add.comments.lower()):
                    to_add.is_qrt = True

        # test data
        # test = Spot()
        # test.activator = "VP5/WD5JR"
        # test.reference = "TC-0001"
        # test.grid6 = "FL31vt"
        # test.spotTime = datetime.utcnow()
        # test.spotter = "HUNTERLOG"
        # test.mode = "CW"
        # test.locationDesc = "TC-TC"
        # test.latitude = "21.8022"
        # test.longitude = "-72.17"
        # test.name = "TEST"
        # test.parkName = "TEST"
        # test.comments = "A TEST SPOT FROM HL"
        # test.frequency = "14001.0"
        # test.hunted_bands = ""
        # test.is_qrt = False
        # test.hunted = False
        # self.session.add(test)
        self.session.commit()

    def update_spot_comments(self, spot_comments_json):
        schema = SpotCommentSchema()
        for s in spot_comments_json:
            to_add = schema.load(s, session=self.session)
            self.session.add(to_add)
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

    def get_spots(self):
        terms = self._get_all_filters()
        x = self.session.query(Spot) \
            .filter(sa.and_(*terms)) \
            .all()
        return x
        # return self.session.query(Spot).all()

    def get_spot(self, id: int) -> Spot:
        return self.session.query(Spot).get(id)

    def get_spot_comments(self, activator, park: str) -> List[SpotComment]:
        return self.session.query(SpotComment) \
            .filter(SpotComment.activator == activator,
                    SpotComment.park == park) \
            .order_by(SpotComment.spotTime.desc()) \
            .all()

    def get_by_mode(self, mode: str) -> List[Spot]:
        return self.session.query(Spot).filter(Spot.mode == mode).all()

    def get_by_band(self, band: Bands) -> List[Spot]:
        terms = self._get_all_filters()
        x = self.session.query(Spot) \
            .filter(sa.and_(*terms)) \
            .all()
        return x

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

    def get_activator_hunts(self, callsign: str) -> int:
        return self.session.query(Qso) \
            .filter(Qso.call == callsign) \
            .count()

    def get_user_config(self) -> UserConfig:
        return self.session.query(UserConfig).first()

    def get_qso(self, id: int) -> Qso:
        return self.session.query(Qso).get(id)

    def get_qsos_from_app(self) -> List[Qso]:
        x = self.session.query(Qso) \
            .filter(Qso.from_app == True).all()   # noqa E712
        return x

    def get_version(self) -> str:
        sql = 'SELECT version_num FROM alembic_version'
        v = self.session.execute(sa.text(sql))
        return v.fetchone()[0]

    def insert_qso(self, qso: Qso, delay_commit: bool = True):
        self.session.add(qso)
        if not delay_commit:
            self.session.commit()

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
        s = self.get_spot(spot_id)
        if (s is None):
            q = Qso()
            q.comment = "Error no spot"
            return q
        a = self.get_activator(s.activator)
        if s is not None:
            q = Qso()
            q.init_from_spot(s, a.name)
            return q

    def log_qso(self, qso: any) -> int:
        '''
        Logs the QSO passed in from UI.

        :param any qso: json from the frontend.
        '''

        def trim_z(input: str):
            temp: str = input
            if temp.endswith('Z'):
                # fromisoformat doesnt like trailing Z
                temp = temp[:-1]
            return temp

        # passing in the QSO object from init_from_spot
        # doesn't seem to ever work. recreate a QSO object
        # and add it directly
        logging.debug(f"inserting qso: {qso}")
        q = Qso()
        q.call = qso['call']
        q.rst_sent = qso['rst_sent']
        q.rst_recv = qso['rst_recv']
        q.freq = qso['freq']
        q.freq_rx = qso['freq_rx']
        q.mode = qso['mode']
        q.comment = qso['comment']
        temp: str = trim_z(qso['qso_date'])
        q.qso_date = datetime.fromisoformat(temp)
        temp: str = trim_z(qso['time_on'])
        q.time_on = datetime.fromisoformat(temp)
        q.tx_pwr = qso['tx_pwr']
        q.rx_pwr = qso['rx_pwr']
        q.gridsquare = qso['gridsquare']
        q.state = qso['state']
        q.sig = qso['sig']
        q.sig_info = qso['sig_info']
        q.from_app = True
        q.cnfm_hunt = False
        self.session.add(q)
        self.session.commit()
        return q.qso_id

    def update_park_data(self, park: any):
        '''
        Parks added from stats do not have anything besides hunt count and
        the reference. This method updates the rest of the data.

        :param any park: the json for a POTA park returned from POTA api
        '''
        if park is None:
            return

        schema = ParkSchema()
        p = self.get_park(park['reference'])

        if p is None:
            logging.debug(f"inserting new {park['reference']}")
            to_add: Park = schema.load(park, session=self.session)
            logging.debug(to_add)
            self.session.add(to_add)
            p = to_add
        else:
            logging.debug(f"updating data for for park {p.reference}")
            p.name = park['name']
            p.grid4 = park['grid4']
            p.grid6 = park['grid6']
            p.active = park['active']
            p.latitude = park['latitude']
            p.longitude = park['longitude']
            p.parkComments = park['parkComments']
            p.accessibility = park['accessibility']
            p.sensitivity = park['sensitivity']
            p.accessMethods = park['accessMethods']
            p.activationMethods = park['activationMethods']
            p.agencies = park['agencies']
            p.agencyURLs = park['agencyURLs']
            p.parkURLs = park['parkURLs']
            p.parktypeId = park['parktypeId']
            p.parktypeDesc = park['parktypeDesc']
            p.locationDesc = park['locationDesc']
            p.locationName = park['locationName']
            p.entityId = park['entityId']
            p.entityName = park['entityName']
            p.referencePrefix = park['referencePrefix']
            p.entityDeleted = park['entityDeleted']
            p.firstActivator = park['firstActivator']
            p.firstActivationDate = park['firstActivationDate']
            p.firstActivationDate = park['firstActivationDate']
            p.website = park['website']

        self.session.commit()

    def inc_park_hunt(self, park: any):
        '''
        Increment the hunt count of a park by one. If park is not in db add it.

        :param any park: the json for a POTA park returned from POTA api
        '''
        schema = ParkSchema()
        if park is None:
            # user logged something w/o a park
            return
        p = self.get_park(park['reference'])

        if p is None:
            logging.debug(f"adding new park row for {park['reference']}")
            to_add: Park = schema.load(park, session=self.session)
            to_add.hunts = 1
            logging.debug(to_add)
            self.session.add(to_add)
            p = to_add
        else:
            logging.debug(f"increment hunts for park {p.reference}")
            p.hunts += 1
            schema.load(park, session=self.session, instance=p)

        self.session.commit()

    def update_park_hunts(self, park: any, hunts: int,
                          delay_commit: bool = True):
        '''
        Update the hunts field of a park in the db with the given hunt. Will
        create a park row if none exists

        :param any park: park json/dic
        :param int hunts: new hunts value
        :param bool delay_commit: if true will not call session.commit
        '''
        schema = ParkSchema()
        obj = self.get_park(park['reference'])

        if obj is None:
            # logging.debug(f"adding new park row for {park}")
            # to_add: Park = schema.load(park, session=self.session)
            to_add = Park()
            to_add.reference = park['reference']
            to_add.hunts = hunts
            # logging.debug(to_add)
            self.session.add(to_add)
            obj = to_add
        else:
            # logging.debug(f"increment hunts for park {obj.reference}")
            # if this was hunted in the app and the the stats are imported
            # this will overwrite and may clear previous hunts
            obj.hunts = hunts
            schema.load(park, session=self.session, instance=obj)

        if not delay_commit:
            self.session.commit()

    def get_park(self, park: str) -> Park:
        return self.session.query(Park) \
            .filter(Park.reference == park) \
            .first()

    def get_op_qso_count(self, call: str) -> int:
        return self.session.query(Qso) \
            .filter(Qso.call == call) \
            .count()

    def get_spot_hunted_flag(self,
                             activator: str,
                             freq: str,
                             ref: str) -> bool:
        '''
        Gets the flag indicating if a given spot has been hunted already today

        :param str activator: activators callsign
        :param str freq: frequency in MHz
        :param str ref: the park reference (ex K-7465)
        :returns true if the spot has already been hunted
        '''
        now = datetime.utcnow()
        band = get_band(freq)
        # logging.debug(f"using band {band} for freq {freq}")
        if band is not None:
            terms = self._get_band_lmt_terms(band, Qso.freq)
        else:
            terms = [1 == 1]

        flag = self.session.query(Qso) \
            .filter(Qso.call == activator,
                    Qso.time_on > now.date(),
                    Qso.sig_info == ref,
                    sa.and_(*terms)) \
            .count() > 0
        return flag

    def get_spot_hunted_bands(self, activator: str, ref: str) -> str:
        '''
        Gets the string of all hunted bands, this spot has been hunted today

        :param str activator: activators callsign
        :param str ref: park reference
        :returns list of hunted bands for today
        '''
        now = datetime.utcnow()
        result = ""
        hunted_b = []

        qsos = self.session.query(Qso) \
            .filter(Qso.call == activator,
                    Qso.sig_info == ref,
                    Qso.time_on > now.date()) \
            .all()

        for q in qsos:
            band = get_band(q.freq)
            if band is None:
                logging.warn(f"unknown band for freq {q.freq}")
            else:
                hunted_b.append(bandNames[band.value])

        result = ",".join(hunted_b)

        return result

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
        terms = self._get_band_lmt_terms(band, Spot.frequency)
        return terms

    def _get_band_lmt_terms(self, band: Bands, col: sa.Column) \
            -> list[sa.ColumnElement[bool]]:
        ll = bandLimits[band][0]
        ul = bandLimits[band][1]
        terms = [sa.cast(col, sa.Float) < ul,
                 sa.cast(col, sa.Float) > ll]
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

    def _init_alembic_ver(self):
        v = VER_FROM_ALEMBIC
        self.session.execute(sa.text('DROP TABLE IF EXISTS alembic_version;'))
        self.session.execute(sa.text('CREATE TABLE alembic_version(version_num varchar(32) NOT NULL);'))  # noqa E501
        self.session.execute(sa.text(f"INSERT INTO alembic_version(version_num) VALUES ('{v}');"))  # noqa E501
        self.session.commit()


if __name__ == "__main__":
    db = DataBase()
    # db.update_spot_comments("KU8T", "K-2263")
    # comments = db.get_spot_comments()
    # print(*text, sep='\n')
