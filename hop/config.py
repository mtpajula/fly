# first_hop/config.py

PORT = "/dev/ttyS0"
BAUD = 57600

GUIDED_NOGPS_MODE = 20
LAND_MODE = 9

ASCENT_DETECT_ALT = 0.25
DESCENT_DETECT_ALT = 0.15

GROUND_STABLE_TIME = 2.0       # seconds
GROUND_EPSILON = 0.03          # 3cm band around lowest altitude
HOVER_TIME = 2.0
ARMING_TIMEOUT = 10.0
MODE_CHANGE_WAIT = 2.0

DISARM_ON_DONE = True      # set False if you want to disable auto-disarm
DISARM_WAIT_TIME = 1.0     # seconds to listen for ACK / status after disarm

# Motor spin test settings
SPIN_THRUST = 0.30       # normalized thrust 0..1 (30% power)
SPIN_THRUST_PERCENT = 35.0   # try 35% first; increase if needed (props OFF)
SPIN_DURATION = 5.0      # seconds to run the spin test

LOOP_DT = 0.1

# How much altitude change from baseline counts as "lifted"
ASCENT_DELTA = 0.25  # meters above the altitude when WAIT_FOR_ASCENT starts


# ---------------- Logging ----------------
LOG_LEVEL = "INFO"       # DEBUG / INFO / WARNING / ERROR
LOG_TO_FILE = False
LOG_FILE_PATH = "first_hop.log"
