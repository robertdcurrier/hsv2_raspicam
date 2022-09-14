#!/usr/bin/env python3
import sys
import signal
import locale
import os
import json
import logging
import time
import datetime
import signal
import sqlite3
import re
import glob
import hashlib
import subprocess
import requests
import paramiko
from getkey import getkey, keys
from picamera import PiCamera, Color
from shutil import copy
from dialog import Dialog
from datetime import date
from time import sleep
from paramiko import SSHClient
from scp import SCPClient
from subprocess import call
# Globals
global CAMERA
global LOGGER
global d
d = Dialog(dialog="dialog")


def update_db(table, setting, value):
    """ Update configurations table in configs.db """
    conn = create_connection()
    cur = conn.cursor()
    sql_text = (""" UPDATE %s set value = '%s' where setting = '%s';""" %
                (table, value, setting))
    cur.execute(sql_text)
    conn.commit()
    cur.close()
    conn.close()


def main_menu():
    """
    Name: main_menu
    Author: robertdcurrier@gmail.com
    Created: 2021-07-05
    Modified: 2022-01-19
    Notes:
    Main menu for HABscope 2.0

    """
    global LOGGER
    global d
    config = get_sql_config('configuration')
    serial = config['serial']
    version = config['version']
    level = config['level']
    mode = config['mode']
    taxa = config['taxa']
    sample_type = config['sample_type']
    # This is a good thing to do at the beginning of your programs.
    locale.setlocale(locale.LC_ALL, '')
    while True:
        # Main menu
        if level == 'Volunteer':
            title = ("Serial: %s  Version: %s" %
                    (serial, version))
        else:
            title = ("Serial: %s  Version: %s  Mode: %s  Taxa: %s" %
                     (serial, version, mode, taxa))


        d.set_background_title(title)
        code, tag = d.menu("Select an Option", 12, 30, 5,
                              choices=[("Preview", ""),
                                          ("Record", ""),
                                          ("Configuration", ""),
                                          ("Exit HABscope", "")],
                              title="HABscope 2.0")
        if tag == 'Preview':
            show_preview()
        elif tag == 'Record':
            outfile = capture_video()

        elif tag == 'Configuration':
            config_menu()
        elif tag == 'Exit HABscope':
            os.system('clear')
            sys.exit()

def config_menu():
    """
    Name: config_menu
    Author: robertdcurrier@gmail.com
    Created: 2021-07-05
    Modified: 2022-01-21
    Notes: Migrated from text config file. Now using sqlite3
    for all configuration management.  This will be long so we
    can keep all together so will not pass lint. Oh darn. :-)
    """
    global d
    config = get_sql_config('configuration')
    level = config['level']
    if level == 'Professional':
        # full menu for pro users
        choices = [
                    ("Serial", ""),
                    ("Mode", ""),
                    ("User Level", ""),
                    ("Fixed/Live", ""),
                    ("Taxa", ""),
                    ("cpL", ""),
                    ("Camera", ""),
                    ("Configuration Password", ""),
                    ("System Password", ""),
                    ("Server Credentials", ""),
                    ("System Update", ""),
                    ("Exit Configuration", "")]
        m_height = 20
        m_title = "%s Configuration Menu" % level.capitalize()

    # reduced menu for volunteers
    if level == 'Volunteer':
         choices = [
                    ("Serial", ""),
                    ("User Level", ""),
                    ("System Update", ""),
                    ("Exit Configuration", "")]
         m_height = 12
         m_title = "%s Configuration Menu" % level.capitalize()

    m_width = 40
    m_rows = len(choices)+1
    while True:
        c_code, c_tag = d.menu(m_title, m_height, m_width, m_rows,
            choices=choices)

        # Bail here
        if c_code == d.CANCEL:
            return
        if c_code == d.OK:
            if c_tag == 'Exit Configuration':
                # Have to call main_menu so we update title bar
                main_menu()
            if c_tag == 'Serial':
                msg = "Enter Serial Number"
                code, resp = d.inputbox(msg, 10, 50)
                if code == d.CANCEL:
                    d.msgbox("Cancelled Changing Serial Number", 10, 50)
                if code == d.OK:
                    is_good = validate_serial(resp)
                    if is_good:
                        update_db("configuration", "serial", resp)
                        msg = "Serial Number changed to %s" % (resp)
                        LOGGER.info(msg)
                        d.msgbox(msg, 10, 50)
                    else:
                        msg = """ Invalid Serial Number! """
                        d.msgbox(msg, 10, 40)
            if c_tag == 'User Level':
                LOGGER.info("Attempting to change user level")
                if level == 'Volunteer':
                    code, pw = d.passwordbox('Enter Password',insecure=True)
                    auth = auth_user(pw)
                    if auth:
                        LOGGER.info("User Level change Password Succeeded")
                    else:
                        d.msgbox("Incorrect Password!")
                        LOGGER.info("Configuration Menu Password Failure")
                        config_menu()
                code, resp = d.menu("Select Type", 12, 40, 5,
                    choices=[("Volunteer", ""),
                            ("Professional", "")])
                if code == d.CANCEL:
                    d.msgbox("Cancelled User Level", 10, 50)
                if code == d.OK:
                    update_db("configuration", "level", resp)

            if c_tag == 'Fixed/Live':
                code, resp = d.menu("Select Type", 12, 40, 5,
                    choices=[("Live", ""),
                            ("Fixed", "")])
                if code == d.CANCEL:
                    d.msgbox("Cancelled Sample Type", 10, 50)
                if code == d.OK:
                    update_db("configuration", "sample_type", resp)

            if c_tag == 'Mode':
                code, resp = d.menu("Select Mode", 12, 40, 5,
                       choices=[("Normal", ""),
                                ("Calibration", ""),
                                ("Training", ""),
                                ("Survey","")])
                if code == d.CANCEL:
                    d.msgbox("Cancelled Mode Change", 10, 50)
                if code == d.OK:
                    update_db("configuration", "mode", resp)
                    msg = "Mode changed to %s" % (resp)
                    LOGGER.info(msg)
                    d.msgbox(msg, 10, 40)

            if c_tag == 'Taxa':
                code, resp = d.menu("Select Taxa", 12, 40, 4,
                    choices=[("Karenia", ""),
                             ("Pyrodinium", ""),
                             ("Alexandrium", "")])
                if code == d.CANCEL:
                    d.msgbox("Cancelled Taxa Change", 10, 50)
                if code == d.OK:
                    update_db("configuration", "taxa", resp)
                    msg = "Taxa changed to %s" % (resp)
                    LOGGER.info(msg)
                    d.msgbox(msg, 10, 40)

            if c_tag == 'cpL':
                config = get_sql_config('configuration')
                msg = "Enter cpL for Calibration"
                code, resp = d.inputbox(msg, 10, 50)
                resp = resp.replace(',','')
                if code == d.CANCEL:
                    d.msgbox("Cancelled cpL Change")
                if code == d.OK:
                    try:
                        resp=int(resp)
                        # No negative cpL
                        if resp < 0:
                            resp = 0
                        update_db("configuration", "cpl", resp)
                        msg = "cp/L Changed to %s" % resp
                        LOGGER.info(msg)
                        d.msgbox(msg, 10, 40)

                    except:
                        LOGGER.info(msg)
                        msg = "Invalid Entry. Must be an integer."
                        d.msgbox(msg, 10, 40)

            if c_tag == 'System Password':
                LOGGER.info("Changing system password")
                code, pw = d.passwordbox("Enter New Password", 10, 50,insecure=True)
                if code == d.CANCEL:
                    d.msgbox("Cancelled System Password Change", 10, 50)
                if code == d.OK:
                    line = 'pi:%s' % pw
                    pfile = open('passwd.txt','w')
                    pfile.write(line)
                    pfile.close()
                    result = os.system("sudo chpasswd -c SHA512 < passwd.txt")
                    if result == 0:
                        LOGGER.info("Succesfully changed system password")
                        d.msgbox('Successfully changed password', 10, 50)
                    else:
                        LOGGER.info("Failed to change system password")
                        d.msgbox('Failed to change password', 10, 50)
                    # remove file so no snooping
                    os.remove('passwd.txt')

            if c_tag == 'Server Credentials':
                d.msgbox("Coming Soon...", 10, 50)
            if c_tag == 'System Update':
                code  = d.yesno("About to Update System! Are you SURE?", 10, 50)
                if code == d.OK:
                    results = system_update()
                    if results:
                        msg = "System Updated. Unit will reboot."
                        LOGGER.info(msg)
                        d.msgbox(msg, 10, 50)
                        config = get_sql_config('configuration')
                        command = config["apt_get"]
                        msg="system_update(): Applying %s" % command
                        LOGGER.info(msg)
                        os.system(command)
                        os.system("sudo reboot")
                    else:
                        msg = "System Update Failed"
                        LOGGER.info(msg)
                        d.msgbox(msg, 10, 50)
                        return
                if code == d.CANCEL:
                    d.msgbox("Cancelled System Update", 10, 50)

                else:
                    msg = "System Update Cancelled"
                    LOGGER.info(msg)
                    d.msgbox("msg", 10, 50)

            if c_tag == 'Camera':
                camera_settings()


def camera_settings():
    """
    Created: 2022-02-14
    Author: robertdcurrier@gmail.com
    Modified: 2022-02-14
    Notes: We need to start working with taxa-specific settings...
    """
    config = get_sql_config('configuration')
    taxa = config['taxa']

    code, resp = d.menu("Camera Settings -- NO ERROR CHECKING!", 22, 45, 12,
            choices=[("camera_contrast", ""),
            ("camera_brightness", ""),
            ("camera_sharpness", ""),
            ("camera_saturation", ""),
            ("camera_awb_mode", ""),
            ("camera_meter_mode", ""),
            ("camera_exposure_mode", ""),
            ("camera_ev", ""),
            ("camera_fps", ""),
            ("camera_preview_size", ""),
            ("Exit", "")])
    if resp == 'Exit':
        # Gotta call it again to pick up changes
        CAMERA.close()
        config_camera()
        main_menu()
    if code == d.CANCEL:
        d.msgbox("Cancelled Camera Settings Update", 10, 50)
        return
    if code == d.OK:
        msg = "Enter Value for %s" % resp
        code, resp2 = d.inputbox(msg, 10, 50)
        if code == d.CANCEL:
            d.msgbox("Cancelled Camera Settings Update", 10, 50)
        else:
            update_db(taxa, resp, resp2)
            msg = "%s changed to %s" % (resp, resp2)
            LOGGER.info(msg)
            d.msgbox(msg, 10, 40)
        # Loop until done changing all settings
        camera_settings()


def check_serial():
    """
    Created: 2022-01-14
    Notes:
    Checks to see if serial is hsv0000 (default)
    and if so, forces user to set serial number.
    """
    global LOGGER
    global d

    LOGGER.info("check_serial(): Making sure serial isn't set to hsv0000")
    config = get_sql_config('configuration')
    serial = config['serial']
    if serial == 'hsv0000':
        msg = "Enter Serial Number"
        code, resp = d.inputbox(msg, 10, 50)
        if code == d.CANCEL:
            d.msgbox("Cancelled Changing Serial Number", 10, 50)
        if code == d.OK:
            is_good = validate_serial(resp)
            if is_good:
                update_db("configuration", "serial", resp)
                msg = "Serial Number changed to %s" % (resp)
                LOGGER.info(msg)
                d.msgbox(msg, 10, 50)
            else:
                msg = """ Invalid Serial Number! """
                d.msgbox(msg, 10, 40)
                check_serial()


def validate_serial(serial):
    """ Make sure we have a valid serial number of the type hsv0001 """
    patt = re.compile('hsv[0-9][0-9][0-9][0-9]')
    match = patt.match(serial)
    if match:
        return True
    else:
        return False


def auth_user(pw):
    """
    Name: auth_user()
    Author: robertdcurrier@gmail.com
    Created: 2018-07-12
    Modified: 2021-07-08
    Notes:
        Copied from HABscope to provide auth for configuration menu
    """
    config = get_sql_config('configuration')
    hash = hashlib.md5(pw.encode())
    if hash.hexdigest() == config["configuration_pw"]:
        return True
    else:
        return False



def mp4_pack():
    """
    Name: mp4_pack()
    Author: robertdcurrier@gmail.com
    Created: 2022-01-12
    Notes:
        2022-01-12 Changed to using MP4Box
        2022-01-24 Added -fps
    """
    global LOGGER
    config = get_sql_config('configuration')
    serial = config["serial"]
    epoch = int(time.time())
    fps = int(config["camera_fps"])
    mode = config["mode"].lower()
    taxa = config["taxa"].lower()
    sample_type = config["sample_type"].lower()
    cpl = int(config["cpl"])
    epoch = int(time.time())

    # Need to check mode and build infile and outfile to match
    if sample_type == 'live':
        outfile = '/data/videos/raw/%s_%d_live_raw.mp4' % (serial, epoch)
    if sample_type == 'fixed':
        outfile = '/data/videos/raw/%s_%d_fixed_raw.mp4' % (serial, epoch)
    if mode == 'calibration':
        outfile = ('/data/videos/calibrations/%s_%s_%s_%d_cal.mp4' %
                   (serial, taxa, cpl, epoch))
    if mode == 'training':
        outfile = ('/data/videos/training/%s_%s_%d_training.mp4' %
                   (serial, taxa, epoch))
    if mode == 'survey':
        outfile = ('/data/videos/surveys/%s_%d_survey.mp4' %
                   (serial, epoch))
    if mode == 'normal':
        outfile = ('/data/videos/raw/%s_%s_%d_raw.mp4' % (serial, taxa, epoch))

    c1 = "MP4Box -add /data/videos/raw/habscope_raw.h264:fps=%d " % (fps)
    c2 = "%s > /dev/null 2>&1 &" % (outfile)
    command = c1 + c2
    LOGGER.info(command)
    os.system(command)
    return(outfile)


def capture_video():
    """
    Name: capture_video()
    Author: robertdcurrier@gmail.com
    Created: 2021-06-30
    Modified: 2022-02-07
    Notes:
    Changed file names so that raw is ONLY for first copy
    no matter the mode. We then use mode in ffmpeg_it and
    upload_file to get outfile names. We now need to update
    view menu item to use real outfile name, not always raw.
    Upload_file should use most_recent of mode type.
    """
    global d
    global LOGGER
    LOGGER.info('capture_video(): Recording started')
    config = get_sql_config('configuration')
    seconds = int(config["record_time"])
    rawdir = config["raw_dir"]
    rawfile = '%s/habscope_raw.h264' % rawdir
    CAMERA.annotate_foreground = Color(config["camera_annotate_foreground"])
    CAMERA.annotate_text_size = int(config["camera_record_text_size"])
    CAMERA.framerate  = int(config["camera_fps"])
    CAMERA.annotate_text = config["camera_warmup_annotate_text"]
    CAMERA.start_preview()
    # Allow camera to warm up
    time.sleep(5)
    # Clear the message
    CAMERA.annotate_text = ""
    CAMERA.start_recording(rawfile)
    CAMERA.wait_recording(seconds)
    CAMERA.stop_recording()
    CAMERA.stop_preview()
    msg = 'capture_video(): Recording completed.'
    LOGGER.info('capture_video(): Recording completed.')
    # Package into MP4 container
    outfile = mp4_pack()
    # wait for mp4_pack() to finish
    while not os.path.exists(outfile):
        sleep(1)
    LOGGER.info('capture_video(): Feeding %s to upload_file' % outfile)
    anal_path = upload_file(outfile)
    results = False
    segment = 0
    msg = 'Analyzing Video'
    d.gauge_start(msg)
    while results == False:
        sleep(5)
        results = get_results(anal_path)
        LOGGER.info('Analysis not complete...')
        segment = segment+5
        d.gauge_update(segment)
        if segment == 100:
            msg = "Unable to retrieve analyzed image..."
            d.msgbox(msg, 5, 50)
            main_menu()
    command = 'gpicview ./habscope_analysis.png'
    os.system(command)


def show_preview():
    """
    Name: show_preview()
    Author: robertdcurrier@gmail.com
    Created: 2021-05-01
    Modified: 2022-01-07
    Notes:


    """
    global LOGGER
    config = get_sql_config('configuration')
    record_width = config["record_width"]
    record_height = config["record_height"]
    LOGGER.info("show_preview(): Started Preview")
    # Set width and height
    CAMERA.annotate_foreground = Color(config["camera_annotate_foreground"])
    CAMERA.annotate_text_size = int(config["camera_preview_annotate_text_size"])
    CAMERA.annotate_text = config["camera_preview_annotate_text"]
    CAMERA.start_preview()
    # Do our own loop here so we can define key to end preview
    while True:
        key = getkey()
        if key == 'q':
            CAMERA.stop_preview()
            CAMERA.annotate_text =''
            LOGGER.info("show_preview(): Stopped Preview")
            return


def config_camera():
    """
    Name: config_camera()
    Author: robertdcurrier@gmail.com
    Created: 2021-05-02
    Modified: 2022-02-15
    Notes: Now working with taxa-specific settings
    """
    global LOGGER
    global CAMERA
    try:
        CAMERA = PiCamera()
    except:
        LOGGER.warning('config_camera(): Failed to open PiCamera!')
        sys.exit()

    config = get_sql_config('configuration')
    taxa = config['taxa']
    camera_config = get_sql_config(taxa)
    # Get crop size params and convert to list of ints
    x1,y1,x2,y2 = config["camera_preview_size"].split(',')
    crop_size = (float(x1),float(y1),float(x2),float(y2))
    record_width = int(config["record_width"])
    record_height = int(config["record_height"])
    CAMERA.zoom = crop_size
    CAMERA.contrast = int(camera_config["camera_contrast"])
    CAMERA.sharpness = int(camera_config["camera_sharpness"])
    CAMERA.brightness = int(camera_config["camera_brightness"])
    CAMERA.saturation = int(camera_config["camera_saturation"])
    CAMERA.exposure_mode = camera_config["camera_exposure_mode"]
    CAMERA.meter_mode = camera_config["camera_meter_mode"]
    CAMERA.exposure_compensation = int(camera_config["camera_ev"])
    CAMERA.resolution=(record_width, record_height)
    CAMERA.sensor_mode=int(camera_config["camera_mode"])



def config_logger():
    """
    Name: config_logger
    Author: robertdcurrier@gmail.com
    Created:    2021-05-12
    Modified:   2021-07-07
    Notes:
        Changed logging format to make shorter

    """
    # Set up logging both console and file
    LOGGER = logging.getLogger('HABscope')
    LOGGER.setLevel(logging.INFO)
    dts = date.today().strftime('%Y-%m-%d')
    logfile = '/data/logs/%s.log' % dts
    formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y/%m/%d %I:%M:%S %p')
    fLOGGER = logging.FileHandler(logfile)
    fLOGGER.setFormatter(formatter)
    LOGGER.addHandler(fLOGGER)
    LOGGER.info("config_logger(): Succesfully configured logging...")
    return LOGGER


def system_update():
    """
    Name: system_updatee()
    Author: robertdcurrier@gmail.com
    Created: 2021-07-12
    Modified: 2022-01-14
    Notes: scp from server to get latest version
    """
    config = get_sql_config('configuration')
    userid=config['userid']
    pw=config['pw']
    server = config['server']
    global LOGGER
    LOGGER.info("system_update(): Attempting system update")
    # Create ssh client
    ssh = SSHClient()
    LOGGER.warning(ssh)
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    LOGGER.warning('system_update(): Set Missing Host Key okay...')

    ssh.connect(server,username=userid, password=pw)
    LOGGER.warning('system_update(): Connected to server okay')
    from_path = "/data/habscope2/updates/habscope_dist/hsv2_raspicam.py"
    out_path = "/home/pi/habscope"

    try:
        with SCPClient(ssh.get_transport()) as scp:
            scp.get(from_path, out_path)
            # Do it again to get config.db as paramiko doesn't support
            # recursive copy
            from_path = "/data/habscope2/updates/habscope_dist/config.db"
            scp.get(from_path, out_path)
            msg = "System Update succeeded"
            LOGGER.info(msg)
            return True
    except scp.SCPException as e:
        msg = "System Update Failed: %s" % e
        LOGGER.warning(msg)
        return False



def upload_file(infile):
    """
    Name: upload_file()
    Author: robertdcurrier@gmail.com
    Created: 2021-06-14
    Modified: 2022-02-16
    Notes: Takes care of scp'ing file to habscope2.gcoos.org
    2022-02-16 Started using infile rather than static file name
    so we don't have to have two copies of raw.mp4 since we now
    pass filename.

    """
    global d
    global LOGGER

    config = get_sql_config('configuration')
    mode = config["mode"].lower()
    taxa = config["taxa"].lower()
    cpl = int(config["cpl"])
    server = config["server"]
    msg = "Uploading file to %s" % server
    LOGGER.info(msg)
    userid = config['userid']
    pw=config['pw']
    serial = config["serial"]
    # These need to be in config store -- sqlitedb file
    cpl = int(config["cpl"])
    epoch = int(time.time())
    # If in survey mode we want to use the most recent file
    if mode == 'survey':
        dir_path = config["survey_dir"]
        survey_files = glob.glob(dir_path + '/*.mp4')
        if len(survey_files) > 0:
            latest_file = max(survey_files, key=os.path.getctime)
            infile = latest_file
            outfile = '%s_%d_survey.mp4' % (serial, epoch)
            outpath = '/data/habscope2/surveys/%s/%s' % (serial, outfile)
            analpath = ''

    # If in calibration mode we want to use the most recent file
    elif mode == 'calibration':
        # code for get most recent cal file
        dir_path = config["cal_dir"]
        cal_files = glob.glob(dir_path + '/*.mp4')
        latest_file = max(cal_files, key=os.path.getctime)

        if len(cal_files) > 0:
            latest_file = max(cal_files, key=os.path.getctime)
            infile = latest_file
            outfile = '%s_%s_%d_%d_calibration.mp4' % (serial, taxa, cpl, epoch)
            outpath = '/data/habscope2/calibrations/%s' % (outfile)
            analpath = ''
        else:
            return

    elif mode == 'training':
            d.msgbox("Training Mode: No Uploads!")
            main_menu()

    # Standard path for volunteer modes of fixed and live
    else:
        dir_path = config["raw_dir"]
        outfile = '%s_%d_%s_%s_raw.mp4' % (serial, epoch, taxa, mode)
        outpath = '/data/habscope2/videos/%s/%s' % (serial, outfile)
        analfile = '%s_%d_%s_%s_pro.png' % (serial, epoch, taxa, mode)
        analpath = '/data/habscope2/videos/%s/%s' % (serial, analfile)
    
    msg = "Uploading file to %s" % server
    d.gauge_start(text=msg)
    # Create progress gauge

    # Create ssh client
    ssh = SSHClient()
    start_time = int(time.time())
    LOGGER.warning(ssh)
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    LOGGER.warning('upload_file(): Set Missing Host Key okay...')

    ssh.connect(server,username=userid, password=pw)
    LOGGER.warning('upoad_file(): Connected to server okay')

    upload_timeout=int(config["upload_timeout"])
    try:
        with SCPClient(ssh.get_transport(), progress=show_progress) as scp:
            scp.put(infile, outpath)
            msg = "Upload to %s succeeded" % server
            LOGGER.info(msg)
            # Close progress gauge
            d.gauge_stop()
            end_time = int(time.time())
        if (end_time - start_time > upload_timeout):
            msg=('Upload Time Limit Exceeded')
            d.msgbox(msg, 10, 50)
            LOGGER.warning(msg)
            return (False, '')
        return (analpath)
    except:
        msg = "Upload to %s failed!" % server
        LOGGER.warning(msg)
        # Close progress gauge
        d.gauge_stop()
        return (False, '')


def show_progress(filename, size, sent):
    """ do what it say """
    global d
    percentage = int(float(sent)/float(size)*100)
    d.gauge_update(percentage)


def create_connection():
    """ create a database connection to the SQLite database """
    global LOGGER
    LOGGER.debug("create_connection(): Opening connection to configuration DB")
    conn = None
    try:
        conn = sqlite3.connect('config.db')
    except Error as e:
        LOGGER.warning(e)
    return conn


def get_results(anal_path):
    """
    Name: get_results()
    Author: robertdcurrier@gmail.com
    Created: 2021-07-19
    Modified: 2022-02-03 got progress gauge working
    Notes:
    """
    global LOGGER
    LOGGER.info('get_results()')
    config = get_sql_config('configuration')
    userid = config['userid']
    pw = config['pw']
    server = config['server']
    upload_timeout=int(config["upload_timeout"])
    msg = "get_results(): Creating ssh client"
    LOGGER.warning(msg)
    ssh = SSHClient()
    start_time = int(time.time())
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    msg = 'get_results(): Set Missing Host Key okay...'
    LOGGER.warning(msg)
    ssh.connect(server,username=userid, password=pw)
    msg = 'get_results(): Connected to server okay'
    LOGGER.warning(msg)
    start_time = int(time.time())
    msg = 'get_results(): Using %s' % anal_path
    LOGGER.warning(msg)
    try:
        with SCPClient(ssh.get_transport(),progress=show_progress) as scp:
            scp.get(anal_path, 'habscope_analysis.png')
            return (True, anal_path)
    except:
        # Keep trying until file appears
            return False


def get_sql_config(table):
    """ 
    Name:       get_sql_config
    Author:     robertdcurrier@gmail.com
    Created:    2021-06-14
    Modified:   2022-02-14
    Notes:      Added table to we could start using 
    taxa-specific camera settings
    """
        
    LOGGER.debug("get_sql_config(%s): Get config values from config.db" % table)
    conn = create_connection()
    cur = conn.cursor()
    configs = {}
    try:
        results = cur.execute('SELECT * from %s' % table)
    except Error as e:
        LOGGER.warning(e)
        sys.exit()
    finally:
        rows = cur.fetchall()
        # Let's make a dict, baby...
        for row in rows:
            configs[row[1]] = row[2]
        return configs
    # Clean up
    conn.close()
    cur.close()


def connected_to_internet(url='http://www.google.com/', timeout=5):
    global LOGGER
    try:
        _ = requests.head(url, timeout=timeout)
        LOGGER.info("connected_to_internet(): True")
        return True
    except requests.ConnectionError:
        LOGGER.info("connected_to_internet(): False")
        return False


def hsp_cli():
    """
    Name: hsp_cli
    Author: robertdcurrier@gmail.com
    Created: 2021-07-01
    Modified: 2021-07-07
    Notes:
    Now using Dialog for menuing. pydialog, actually...

    """
    global LOGGER
    LOGGER = config_logger()
    LOGGER.info("HABscope 2.0 GUI Starting Up...")
    check_serial()
    config_camera()
    INET_STATUS = connected_to_internet()
    main_menu()


if __name__ == '__main__':
    os.system('clear')
    hsp_cli()
