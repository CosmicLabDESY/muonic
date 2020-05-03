"""
Provides DAQ server and connection classes to interface with the serial port.
"""

from __future__ import print_function
import abc
from future.utils import with_metaclass
import logging
import os
import queue
import serial
import subprocess
from time import sleep

try:
    import zmq
except ImportError:
    # DAQMissingDependencyError will be raised when trying to use zmq
    pass

from muonicPro.daq.exceptions import DAQMissingDependencyError

"""
###############################################################################
"""

class BaseDAQConnection(with_metaclass(abc.ABCMeta, object)):
    """
    Base DAQ Connection class.
    Provides serial class object for communication with Daq Card only.
    Does not provide any function for communication. Descending classes
    needed.
    Raises SystemError if serial connection cannot be established.

    Functions:
    ==========

    __init__(logger=None):
        "Initialization"

    get_serial_port():
        "Searches for Daq Card Port and returns a serial object."

    read():
        "Abstract, must be overwritten in descending class.
        Get data from the DAQ"

    write():
        "Abstract, must be overwritten in descending class.
        Put messages from the inqueue which is filled by the DAQ"

    get_dev_path(script):
        "Executes shell programs"



    Attributes:
    ==========
    logger: logger class object
        "Given as argument by init or generated by init."

    running: int
        "Int variable as bool (0 or 1) to controll
         readout loop in the read-function. Set to at __init__"

    serial_port: serial.Serial object
        "Serial connection to the DAQ Card."
    """

    def __init__(self, logger=None):
        """
        Parameters:
        -----------
            logger: logger class object

        Notes:
        ------
            1. Init the logger object if not given by the argument.
            2. Init the serial object 'serial_port' for communication with DAQ Card.
        """
        if logger is None:
            logger = logging.getLogger()
        self.logger = logger
        self.running = 1

        try:
            self.serial_port = self.get_serial_port()
        except serial.SerialException as e:
            self.logger.fatal("SerialException thrown! Value: %s" % e.message)
            raise SystemError(e)

    def get_dev_path(self, script):
        '''
        Runs executable on shell and interpretes output string.

        Parameter:
        ----------

        script: string
            Name of the program.
        '''
        tty = subprocess.Popen(
                [script], stdout=subprocess.PIPE).communicate()[0]

        return "/dev/%s" % tty.decode().rstrip('\n')

    def get_serial_port(self):
        #    def get_serial_port(ID_SERIAL):
        #        """
        #        Returns a the address.
        #        The serial port is connected with an Serial to USB adapter.
        #        The Serial ID of these is
        #        "Prolific_Technology_Inc._USB-Serial_Controller_D",
        #        Minor is the number of one of the two adapter.
        #        """
        #        import pyudev
        #        context = pyudev.Context()
        #        port = None
        #
        #        for device in context.list_devices(
        #                                       subsystem='tty', ID_BUS='usb'):
        #            serial_ID = device['ID_SERIAL']
        #            if serial_ID == ID_SERIAL:
        #                port = device['DEVNAME']
        #
        #    return port
        """
        Check out which device (/dev/tty) is used for DAQ communication.

        Loops the following algorithm as long as connected is False:
        1a. Tries to get path of the DAQ card.
        1b. Just init the serial object to communicate with the card.
        2.  Returns this object.

        Raises OSError if binary 'which_tty_daq' cannot be found.

        Returns:
        --------
            serial.Serial -- serial connection port

        Raises:
        -------
            OSError
        """
        connected = False
        serial_port = None

        while not connected:
            try:
                dev = self.get_dev_path("which_tty_daq")
            except OSError:
                # try using package script ../../bin/which_tty_daq
                which_tty_daq = os.path.abspath(
                        os.path.join(os.path.dirname(__file__), os.pardir,
                                     os.pardir, 'bin', 'which_tty_daq'))

                if not os.path.exists(which_tty_daq):
                    raise OSError("Can not find binary which_tty_daq")

                dev = self.get_dev_path(which_tty_daq)

            self.logger.info("Daq found at %s", dev)
            self.logger.info("trying to connect...")

            try:
                serial_port = serial.Serial(port=dev, baudrate=115200,
                                            bytesize=8, parity='N', stopbits=1,
                                            timeout=0.5, xonxoff=True)
                connected = True
            except serial.SerialException as e:
                self.logger.error(e)
                self.logger.error("Waiting 5 seconds")
                sleep(5)

        self.logger.info("Successfully connected to serial port")

        return serial_port

    @abc.abstractmethod
    def read(self):
        """
        Get data from the DAQ. Read it from the provided Queue.

        Return:
        -------
            None
        """
        return

    @abc.abstractmethod
    def write(self):
        """
        Put messages from the inqueue which is filled by the DAQ

        Return:
        -------
            None
        """
        return

"""
###############################################################################
"""
class DAQConnection(BaseDAQConnection):
    """
    Client connection with DAQ card. It provides functions which passes the in/output via multiprocessing.Queues 
    which are accessable for multprocessing threads.
    Inheritated from BaseDAQConnection.

    Function:
    =========
        __init__(in_queue, out_queue, logger=None):
            "Adds the parameter to the attributes.
            Generates logger class object if it is None."

        read():
            "Reads data from 'serial_port'
            into 'in_queue' in a loop."

        write():
            "Writes data from 'out_queue'
            into the 'serial_port' in a loop."

    Inherited Attributes:
    =====================
    logger: logging.Logger
        "logger class object given as argument by init or generated by init."

    running:
        "Int variable as bool (0 or 1) to controll
         readout loop in the read-function. Set to at __init__."

    serial_port: serial.Serial object
        "Serial connection to the DAQ Card."

    Attributes:
    ===========
    in_queue: multiprocessing.Queue
        "Queue for incoming data. It is actualized every 0.01s or 0.2s."


    out_queue: multiprocessing.Queue
        "Queue for outcoming data. It is actualized every 0.01s or 0.2s."

    """

    def __init__(self, in_queue, out_queue, logger=None):
        super(DAQConnection, self).__init__(logger)
        self.in_queue = in_queue
        self.out_queue = out_queue

    def read(self):
        """
        Get data from the DAQ. Read it into the provided queue out_queue.
        It runs in an endless loop with a frequency 5 to 100 Hz
        and gets therefore online data as long as attribute running is 1.
        """
        min_sleep_time = 0.01  # seconds
        max_sleep_time = 0.2  # seconds
        sleep_time = min_sleep_time  #seconds

        while self.running:
            try:
                if self.serial_port.inWaiting():
                    while self.serial_port.inWaiting():
                        self.out_queue.put((self.serial_port.readline().strip()).decode())
                    sleep_time = max(sleep_time / 2, min_sleep_time)
                else:
                    sleep_time = min(1.5 * sleep_time, max_sleep_time)
                sleep(sleep_time)
            except (IOError, OSError):
                self.logger.error("IOError")
                self.serial_port.close()
                self.serial_port = self.get_serial_port()
                # this has to be implemented in the future
                # for now, we assume that the card does not forget
                # its settings, only because the USB connection is
                # broken
                # self.setup_daq.setup(self.commandqueue)

    def write(self):
        """
        Put messages from the inqueue which is filled by the DAQ
        It runs in an endless loop with a frequency 10 Hz
        as long as the attribute running is 1. Data is send via serial object
        if and only if the attribute 'in_queue' has a qsize > 0.
        """
        while self.running:
            try:
                while self.in_queue.qsize():
                    try:
                        self.serial_port.write((str(self.in_queue.get(0)) +
                                               "\r").encode())
                    except (queue.Empty, serial.SerialTimeoutException):
                        pass
            except NotImplementedError:
                self.logger.debug("Running Mac version of muonic.")
                while True:
                    try:
                        self.serial_port.write((str(self.in_queue.get(
                                timeout=0.01)) + "\r").encode())
                    except (queue.Empty, serial.SerialTimeoutException):
                        pass
            sleep(0.1)

"""
###############################################################################
"""
class DAQServer(BaseDAQConnection):
    """
    DAQ server
    Class to communicate with DAQ Card. The read and
    write functions are executed in a loop. The communication works
    via the attribute 'socket' which is a 'zmq.Context().socket'
    object.

    Raises DAQMissingDependencyError if zmq is not installed.

    Inheritated from BaseDAQConnection.

    Parameter:
    ==========
    address: string
        Address to listen on, default='127.0.0.1'

    port: int
        TCP port to listen on, default=5556

    logger: logger object
        default=None

    Functions:
    =========
        __init__(address='127.0.0.1', port=5556, logger=None):
            "Adds the parameter to the attributes.
            Generates logger class object if it is None."

        read():
            "Reads data from 'serial_port'
            into 'socket' in a loop."

        write():
            "Writes data from 'socket'
            into the 'serial_port' in a loop."

        serve():
            Runs the server. That means the read and write functions.


    Inherited Attributes:
    =====================
    logger: logging.Logger
        "logger class object given as argument by init or generated by init."

    running:
        "Int variable as bool (0 or 1) to controll
         readout loop in the read-function. Set to at __init__."

    serial_port: serial.Serial object
        "Serial connection to the DAQ Card."

    Attributes:
    ===========
    socket: zmq.Context().socket
        ""

    """

    def __init__(self, address='127.0.0.1', port=5556, logger=None):
        super(DAQServer, self).__init__(self, logger)  # is'nt that redundant?
        try:
            self.socket = zmq.Context().socket(zmq.PAIR)
            self.socket.bind("tcp://%s:%d" % (address, port))
        except NameError:
            raise DAQMissingDependencyError("no zmq installed...")

    def serve(self):
        """
        Runs the server
        In some way the loops here
        are redundant.
        """
        while True:
            self.read()
            self.write()

    def read(self):
        """
        Get data from the DAQ. Sends it into the provided socket.
        It runs in an endless loop with a frequency 5 to 100 Hz
        and gets therefore online data as long as attribute running is 1.
        """
        min_sleep_time = 0.01  # seconds
        max_sleep_time = 0.2  # seconds
        sleep_time = min_sleep_time  # seconds
        while self.running:
            try:
                if self.serial_port.inWaiting():
                    while self.serial_port.inWaiting():
                        self.socket.send((self.serial_port.readline().strip()).decode())
                    sleep_time = max(sleep_time / 2, min_sleep_time)
                else:
                    sleep_time = min(1.5 * sleep_time, max_sleep_time)
                sleep(sleep_time)
            except (IOError, OSError):
                self.logger.error("IOError")
                self.serial_port.close()
                self.serial_port = self.get_serial_port()
                # this has to be implemented in the future
                # for now, we assume that the card does not forget
                # its settings, only because the USB connection is
                # broken
                # self.setup_daq.setup(self.commandqueue)

    def write(self):
        """
        Put messages from the inqueue which is filled by the DAQ
        It runs in an endless loop with a frequency 10 Hz
        as long as the attribute running is 1.
        """
        while self.running:
            msg = self.socket.recv_string()
            self.serial_port.write((str(msg) + "\r").encode())
            sleep(0.1)


if __name__ == "__main__":
    logger = logging.getLogger()
    server = DAQServer(port=5556, logger=logger)
    server.serve()
