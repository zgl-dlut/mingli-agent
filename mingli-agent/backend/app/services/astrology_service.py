from datetime import datetime
from typing import Dict, List

from pydantic import BaseModel
from flatlib import const
from flatlib import chart as charts
from flatlib.datetime import Datetime
from flatlib.geopos import GeoPos


class PlanetPosition(BaseModel):
    name: str
    sign: str
    degree: float
    retrograde: bool


class HouseCusp(BaseModel):
    number: int
    sign: str
    degree: float


class Aspect(BaseModel):
    planet1: str
    planet2: str
    aspect_type: str
    orb: float


class AstrologyChart(BaseModel):
    sun_sign: str
    sun_degree: float
    moon_sign: str
    moon_degree: float
    ascendant: str
    mc_sign: str
    planets: List[PlanetPosition]
    houses: List[HouseCusp]
    aspects: List[Aspect]
    element_distribution: Dict[str, int]
    mode_distribution: Dict[str, int]


SIGN_ELEMENTS = {
    "Aries": "火", "Taurus": "土", "Gemini": "风", "Cancer": "水",
    "Leo": "火", "Virgo": "土", "Libra": "风", "Scorpio": "水",
    "Sagittarius": "火", "Capricorn": "土", "Aquarius": "风", "Pisces": "水",
}

SIGN_MODES = {
    "Aries": "开创", "Taurus": "固定", "Gemini": "变动",
    "Cancer": "开创", "Leo": "固定", "Virgo": "变动",
    "Libra": "开创", "Scorpio": "固定", "Sagittarius": "变动",
    "Capricorn": "开创", "Aquarius": "固定", "Pisces": "变动",
}

PLANET_NAMES = {
    "Sun": "太阳", "Moon": "月亮", "Mercury": "水星", "Venus": "金星",
    "Mars": "火星", "Jupiter": "木星", "Saturn": "土星",
    "Uranus": "天王星", "Neptune": "海王星", "Pluto": "冥王星",
}

ASPECT_TYPES = {
    0: "合相", 30: "十二分相", 45: "八分相", 60: "六分相",
    90: "四分相", 120: "三分相", 135: "补八分相", 150: "补十二分相", 180: "对分相",
}


def format_degree(degree: float) -> float:
    return round(degree, 2)


def calculate_element_distribution(planets: List[PlanetPosition]) -> Dict[str, int]:
    elements = {"火": 0, "土": 0, "风": 0, "水": 0}
    for planet in planets:
        elements[SIGN_ELEMENTS.get(planet.sign, "风")] += 1
    return elements


def calculate_mode_distribution(planets: List[PlanetPosition]) -> Dict[str, int]:
    modes = {"开创": 0, "固定": 0, "变动": 0}
    for planet in planets:
        modes[SIGN_MODES.get(planet.sign, "变动")] += 1
    return modes


def calculate_aspects(chart) -> List[Aspect]:
    aspects = []
    major_aspects = [0, 60, 90, 120, 180]
    planets_list = [const.SUN, const.MOON, const.MERCURY, const.VENUS, const.MARS,
                    const.JUPITER, const.SATURN]

    for i, p1 in enumerate(planets_list):
        for j in range(i + 1, len(planets_list)):
            p2 = planets_list[j]
            obj1 = chart.get(p1)
            obj2 = chart.get(p2)
            angle = abs(obj1.lon - obj2.lon)
            if angle > 180:
                angle = 360 - angle
            for aspect_angle in major_aspects:
                orb = abs(angle - aspect_angle)
                if orb < 8:
                    aspects.append(Aspect(
                        planet1=PLANET_NAMES.get(p1, p1),
                        planet2=PLANET_NAMES.get(p2, p2),
                        aspect_type=ASPECT_TYPES.get(aspect_angle, str(aspect_angle)),
                        orb=round(orb, 2),
                    ))
                    break
    return aspects


def calculate_astrology(birth_date: str, birth_time: str, latitude: float, longitude: float) -> AstrologyChart:
    birth_datetime = datetime.strptime(f"{birth_date} {birth_time}", "%Y-%m-%d %H:%M")
    tz_hours = int(longitude / 15)
    tz_mins = int((longitude / 15 - tz_hours) * 60)

    flat_datetime = Datetime(
        f"{birth_datetime.year}/{birth_datetime.month}/{birth_datetime.day}",
        f"{birth_datetime.hour}:{birth_datetime.minute:02d}",
        f"+{tz_hours}:{tz_mins:02d}"
    )

    lat_deg = int(abs(latitude))
    lat_min = int((abs(latitude) - lat_deg) * 60)
    lng_deg = int(abs(longitude))
    lng_min = int((abs(longitude) - lng_deg) * 60)
    geopos = GeoPos(f"{lat_deg}:{lat_min:02d}", f"{lng_deg}:{lng_min:02d}")

    chart = charts.Chart(flat_datetime, geopos, hsys=const.HOUSES_PLACIDUS)

    sun = chart.get(const.SUN)
    moon = chart.get(const.MOON)
    ascendant = chart.get(const.ASC)
    mc = chart.get(const.MC)

    planets_list = [const.SUN, const.MOON, const.MERCURY, const.VENUS, const.MARS,
                    const.JUPITER, const.SATURN]

    planets = []
    for p in planets_list:
        planet = chart.get(p)
        planets.append(PlanetPosition(
            name=PLANET_NAMES.get(p, p),
            sign=planet.sign,
            degree=format_degree(planet.lon),
            retrograde=getattr(planet, 'isRetrograde', False)(),
        ))

    houses = []
    for i in range(1, 13):
        house = chart.houses.get(f'House{i}')
        if house:
            houses.append(HouseCusp(
                number=i,
                sign=house.sign,
                degree=format_degree(house.lon),
            ))

    aspects = calculate_aspects(chart)

    element_distribution = calculate_element_distribution(planets)
    mode_distribution = calculate_mode_distribution(planets)

    return AstrologyChart(
        sun_sign=sun.sign,
        sun_degree=format_degree(sun.lon),
        moon_sign=moon.sign,
        moon_degree=format_degree(moon.lon),
        ascendant=ascendant.sign,
        mc_sign=mc.sign,
        planets=planets,
        houses=houses,
        aspects=aspects,
        element_distribution=element_distribution,
        mode_distribution=mode_distribution,
    )
