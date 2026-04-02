from enum import Enum

class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    WAIT = "WAIT"

class VoteType(str, Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    NEUTRAL = "NEUTRAL"
    WARN = "WARN"

class SignalStrength(str, Enum):
    STRONG = "STRONG"
    WEAK = "WEAK"
    NONE = "NONE"

class Session(str, Enum):
    ASIA = "ASIA"
    EUROPE = "EUROPE"
    US = "US"

class Timeframe(str, Enum):
    H1 = "1H"
    H4 = "4H"
    D1 = "1D"
    W1 = "1W"

class IndicatorCategory(str, Enum):
    ORDER_FLOW = "ORDER_FLOW"
    MACRO_DERIVATIVES = "MACRO_DERIVATIVES"
    ON_CHAIN = "ON_CHAIN"
    SENTIMENT = "SENTIMENT"
    TECHNICAL = "TECHNICAL"
    VOLATILITY = "VOLATILITY"
