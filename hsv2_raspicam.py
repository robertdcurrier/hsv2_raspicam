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
import numpy as np
import cv2 as cv2
from getkey import getkey, keys
from picamera import PiCamera, Color
from shutil import copy
from dialog import Dialog
from datetime import date
from time import sleep
from paramiko import SSHClient
from scp import SCPClient
from subprocess import call
from PIL import Image
# Globals
global CAMERA
global d
d = Dialog(dialog="dialog")


def update_db(table, setting, value):
    """ Update configurations table in configs.db """
    conn = create_connection('./config.db')
    cur = conn.cursor()
    sql_text = (""" UPDATE %s set value = '%s' where setting = '%s';""" %
                (table, value, setting))
    cur.execute(sql_text)
    conn.commit()
    cur.close()
    conn.close()
    logging.info(sql_text)


def main_menu():
    """
    Name: main_menu
    Author: robertdcurrier@gmail.com
    Created: 2021-07-05
    Modified: 2022-01-19
    Notes:
    Main menu for HABscope 2.0

    """
    global d
    config = get_sql_config('configuration')
    serial = config['serial']
    version = config['version']
    level = config['level']
    mode = config['mode']
    taxa = config['taxa']
    # 2022-07-13 robertdcurrier@gmail.com
    # We need to provide a Menu name to internal name mapping in config.db
    if taxa == 'alexandriumCatenella':
        menu_taxa = 'Alexandrium catenella'
    if taxa == 'alexandriumMonilatum':
        menu_taxa = 'Alexandrium monilatum'
    if taxa == 'kareniaBrevis':
        menu_taxa = 'Karenia brevis'
    if taxa == 'pyrodiniumBahamense':
        menu_taxa = 'Pyrodinium bahamense'

    sample_type = config['sample_type']
    # This is a good thing to do at the beginning of your programs.
    locale.setlocale(locale.LC_ALL, '')
    INET_STATUS = connected_to_internet()
    if INET_STATUS == False:
        if mode  != 'Survey':
            d.msgbox('No Internet Service. Classification disabled.')
    if INET_STATUS and config['server'] == 'habscope2.gcoos.org':
        rsync_logs()

    while True:
        # Main menu
        if level == 'Volunteer':
            title = ("Serial: %s Version: %s Taxa: %s Internet: %s" %
                    (serial, version, menu_taxa, INET_STATUS))
        else:
            title = ("%s %s %s %s %s" %
                     (serial, version, mode, menu_taxa, INET_STATUS))


        d.set_background_title(title)
        code, tag = d.menu("Select an Option", 12, 35, 4,
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
                    ("Server", ""),
                    ("Mode", ""),
                    ("User Level", ""),
                    ("Fixed/Live", ""),
                    ("Taxa", ""),
                    ("Camera", ""),
                    ("Recording Time", ""),
                    ("Configuration Password", ""),
                    ("System Password", ""),
                    ("Server Credentials", ""),
                    ("System Update", ""),
                    ("Exit Configuration", "")]
        m_height = 22
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

            if c_tag == 'Server':
                msg = "Enter Server Name"
                code, resp = d.inputbox(msg, 10, 50)
                if code == d.CANCEL:
                    d.msgbox("Cancelled Changing Server Name", 10, 50)
                if code == d.OK:
                    update_db("configuration", "server", resp)
                    msg = "Server Name changed to %s" % (resp)
                    logging.info(msg)
                    d.msgbox(msg, 10, 50)

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
                        logging.info(msg)
                        d.msgbox(msg, 10, 50)
                    else:
                        msg = """ Invalid Serial Number! """
                        d.msgbox(msg, 10, 40)
            if c_tag == 'User Level':
                logging.info("Attempting to change user level")
                if level == 'Volunteer':
                    code, pw = d.passwordbox('Enter Password',insecure=True)
                    auth = auth_user(pw)
                    if auth:
                        logging.info("User Level change Password Succeeded")
                    else:
                        d.msgbox("Incorrect Password!")
                        logging.info("Configuration Menu Password Failure")
                        config_menu()
                code, resp = d.menu("Select Type", 12, 40, 5,
                    choices=[("Volunteer", ""),
                            ("Professional", "")])
                if code == d.CANCEL:
                    d.msgbox("Cancelled User Level", 10, 50)
                if code == d.OK:
                    update_db("configuration", "level", resp)

            if c_tag == 'Recording Time':
                msg = "Recording Length in Seconds"
                code, resp = d.inputbox(msg, 10, 50)
                if code == d.CANCEL:
                    d.msgbox("Cancelled Recording Seconds", 10, 50)
                if code == d.OK:
                    resp = int(resp)
                    update_db("configuration", "record_time", resp)

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
                    logging.info(msg)
                    d.msgbox(msg, 10, 40)

            if c_tag == 'Taxa':
                code, resp = d.menu("Select Taxa", 12, 40, 4,
                    choices=[("Karenia brevis", ""),
                             ("Pyrodinium bahamense", ""),
                             ("Alexandrium catenella", ""),
                             ("Alexandrium monilatum", ""),
                             ("Detritus", "")])
                if code == d.CANCEL:
                    d.msgbox("Cancelled Taxa Change", 10, 50)
                if code == d.OK:
                    # 2022-07-13 robertdcurrier@gmail.com
                    # Need to rename to single string naming convention
                    # We will eventually want to have a table in config.db
                    # with Menu name to internal name mappings...
                    if resp == 'Alexandrium catenella':
                        resp = 'alexandriumCatenella'
                    if resp == 'Alexandrium monilatum':
                        resp = 'alexandriumMonilatum'
                    if resp == 'Karenia brevis':
                        resp = 'kareniaBrevis'
                    if resp == 'Pyrodinium bahamense':
                        resp = 'pyrodiniumBahamense'

                    update_db("configuration", "taxa", resp)
                    msg = "Taxa changed to %s" % (resp)
                    logging.info(msg)
                    d.msgbox(msg, 10, 40)

            if c_tag == 'System Password':
                logging.info("Changing system password")
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
                        logging.info("Succesfully changed system password")
                        d.msgbox('Successfully changed password', 10, 50)
                    else:
                        logging.info("Failed to change system password")
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
                        logging.info(msg)
                        d.msgbox(msg, 10, 50)
                        config = get_sql_config('configuration')
                        command = config["apt_get"]
                        msg="system_update(): Applying %s" % command
                        logging.info(msg)
                        os.system(command)
                        os.system("sudo reboot")
                    else:
                        msg = "System Update Failed"
                        logging.info(msg)
                        d.msgbox(msg, 10, 50)
                        return
                if code == d.CANCEL:
                    d.msgbox("Cancelled System Update", 10, 50)

                else:
                    msg = "System Update Cancelled"
                    logging.info(msg)
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
            logging.info(msg)
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
    global d

    logging.info("check_serial(): Making sure serial isn't set to hsv0000")
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
                logging.info(msg)
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
        2022-03-22 Added coordinates to outfile name
    """
    config = get_sql_config('configuration')
    serial = config["serial"]
    epoch = int(time.time())
    fps = int(config["camera_fps"])
    mode = config["mode"].lower()
    taxa = config["taxa"]
    # leading char only
    taxa[0].lower()
    sample_type = config["sample_type"].lower()
    epoch = int(time.time())


    # Need to check mode and build infile and outfile to match
    if mode == 'calibration':
        cpl = get_cpl()
        msg = 'mp4_pack(): Got cpl of %s' % cpl
        logging.info(msg)
        outfile = ('/data/videos/calibrations/%s_%s_%s_%d_cal.mp4' %
                   (serial, taxa, cpl, epoch))
    if mode == 'training':
        outfile = ('/data/videos/training/%s_%s_%d_training.mp4' %
                   (serial, taxa, epoch))
    if mode == 'survey':
        (lat, lon, site) = lat_lon_menu()
        outfile = ('/data/videos/surveys/%s_%d_%08.4f_%09.4f_raw.mp4' %
                   (serial, epoch, lat, lon))

    if mode == 'normal':
        #(lat, lon, site) = lat_lon_menu()
        #outfile = ('/data/videos/raw/%s_%s_%d_%08.4f_%09.4f_raw.mp4' %
        #           (serial, taxa, epoch, lat, lon))
        (lat, lon, site) = lat_lon_menu()
        site = site.replace(' ','-')
        outfile = ("/data/videos/raw/%s_%s_%d_%08.4f_%09.4f_%s_raw.mp4" %
                   (serial, taxa, epoch, lat, lon, site))

    c1 = "MP4Box -add /data/videos/raw/habscope_raw.h264:fps=%d " % (fps)
    c2 = "%s > /dev/null 2>&1 &" % (outfile)
    command = c1 + c2
    logging.info(command)
    os.system(command)
    return(outfile)


def capture_video():
    """
    Name: capture_video()
    Author: robertdcurrier@gmail.com
    Created: 2021-06-30
    Modified: 2022-03-21
    Notes:
    Changed file names so that raw is ONLY for first copy
    no matter the mode. We then use mode in ffmpeg_it and
    upload_file to get outfile names. We now need to update
    view menu item to use real outfile name, not always raw.
    Upload_file should use most_recent of mode type.

    2022-03-21: Switched from 'habscope_analysis.png' to real file name
    in /data/images'
    """
    global d
    logging.info('capture_video(): Recording started')
    config = get_sql_config('configuration')
    mode = config['mode']
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
    logging.info('capture_video(): Recording completed.')
    # Package into MP4 container
    outfile = mp4_pack()
    # wait for mp4_pack() to finish
    while not os.path.exists(outfile):
        sleep(1)

    mode = config["mode"].lower()
    INET_STATUS = connected_to_internet()
    # For calibration we want to upload video, not process onboard
    if mode == 'normal' or mode == 'calibration':
        if not INET_STATUS:
            msg = "No Internet. Can't Upload"
            d.msgbox(msg, 5, 50)
            main_menu()

        upload_video(outfile)
        #CODEMONKEY LIKE FRITOS
        main_menu()


def upload_video(infile):
    """
    Name: upload_video()
    Author: robertdcurrier@gmail.com
    Created: 2021-06-14
    Modified: 2022-05-04
    Notes: Takes care of scp'ing file to habscope2.gcoos.org
    2022-02-16 Started using infile rather than static file name
    so we don't have to have two copies of raw.mp4 since we now
    pass filename.
    2022-05-04 Reverted to uploading full video. Needed to tweak analpath
    """
    global d
    logging.info('upload_video(%s)' % infile)
    config = get_sql_config('configuration')
    serial = config["serial"]
    mode = config["mode"].lower()
    server = config["server"]
    msg = "upload_video(): Uploading file to %s" % server
    logging.info(msg)
    userid = config['userid']
    pw=config['pw']

    epoch = int(time.time())
    msg = "upload_video(): Uploading %s to %s" % (infile, server)
    logging.info(msg)

    # Create progress gauge
    msg = "Uploading video to %s" % server
    d.gauge_start(text=msg)

    # Create ssh client
    ssh = SSHClient()
    start_time = int(time.time())
    logging.warning(ssh)
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    logging.info('upload_video(): Set Missing Host Key okay...')

    ssh.connect(server,username=userid, password=pw)
    logging.info('upload_video(): Connected to server okay')

    upload_timeout=int(config["upload_timeout"])
    (root_path, file_name) = os.path.split(infile)
    if mode == 'calibration':
        outpath = '/data/habscope2/calibrations/%s' % file_name
    if mode == 'normal':
        outpath = '/data/habscope2/videos/%s/%s' % (serial, file_name)

    msg = 'upload_video(): Sending %s to %s' % (infile, outpath)
    logging.info(msg)
    try:
        with SCPClient(ssh.get_transport(), progress=show_progress) as scp:
            scp.put(infile, outpath)
            msg = "Upload to %s succeeded" % server
            logging.info(msg)
            # Close progress gauge
            d.gauge_stop()
            # We have to set the filename of the classified image, so we
            # change from mp4 to png and pro from raw. Necessary so we can
            # retrieve the image from the server
            analpath = outpath.replace('mp4', 'png')
            analpath = analpath.replace('raw', 'pro')
            return analpath

            end_time = int(time.time())
        if (end_time - start_time > upload_timeout):
            msg=('Upload Time Limit Exceeded')
            d.msgbox(msg, 10, 50)
            logging.warning(msg)
            return (False, '')
    except:
        msg = "Upload to %s failed!" % server
        logging.warning(msg)
        # Close progress gauge
        d.gauge_stop()
        return (False, '')


def get_cpl():
    """
    Name:       get_cpl()
    Author:     robertdcurrier@gmail.com
    Created:    2022-03-28
    Modified:   2022-03-28
    Notes:      Gets cpl for calibrations
    """
    msg = 'Coulter cpL'
    code, resp = d.inputbox(msg, 10,30)
    if code == d.OK:
        if resp.isdigit():
            return resp
        else:
            d.msgbox('Bad cpL', 10, 30)
            cpl = get_cpl()
            return(cpl)


def upload_still(outfile):
    """
    Name:       upload_still
    Author:     robertdcurrier@gmail.com
    Created:    2022-02-21
    Modified:   2022-03-15
    Notes:      Here we upload a STILL images instead of a 30 second video.
    This will be a much faster upload, hopefully solving problems at FWRI.
    We will also be able to make the classier on habscope2.gcoos.org much
    simpler as there will be no video processing -- just classifying an image.
    """
    global d
    logging.info("upload_still(): Got %s" % outfile)

    config = get_sql_config('configuration')
    mode = config["mode"].lower()
    taxa = config["taxa"].lower()
    cpl = int(config["cpl"])
    server = config["server"]
    msg = "Uploading file to %s" % server
    logging.info(msg)
    userid = config['userid']
    pw=config['pw']
    serial = config["serial"]
    # These need to be in config store -- sqlitedb file
    epoch = int(time.time())

    # TO DO: Fix outpath to reflect proper destination using os.path.split()
    (root_path, file_name) = os.path.split(outfile)
    outpath = '/data/habscope2/images/%s/%s' % (serial, file_name)
    analpath = outpath.replace('raw','pro')
    logging.info('upload_file: outpath is %s' % outpath)
    logging.info('upload_file: analpath is %s'%  analpath)
    msg = "Uploading image to %s" % (server)

    d.gauge_start(text=msg)

    # Create ssh client
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    logging.warning('upload_file(): Set Missing Host Key okay...')

    ssh.connect(server,username=userid, password=pw)
    logging.info('upload_file(): Connected to server okay')
    logging.info('upload_file(): Sending %s to %s' % (outfile, outpath))
    upload_timeout=int(config["upload_timeout"])
    try:
        with SCPClient(ssh.get_transport(), progress=show_progress) as scp:
            scp.put(outfile, outpath)
            msg = "Upload to %s succeeded" % server
            logging.info(msg)
            # Close progress gauge
            d.gauge_stop()
        return (analpath)
    except:
        msg = "Upload to %s failed!" % server
        logging.warning(msg)
        # Close progress gauge
        d.gauge_stop()
        return (False, '')


def show_preview():
    """
    Name: show_preview()
    Author: robertdcurrier@gmail.com
    Created: 2021-05-01
    Modified: 2022-01-07
    Notes:


    """
    config = get_sql_config('configuration')
    record_width = config["record_width"]
    record_height = config["record_height"]
    logging.info("show_preview(): Started Preview")
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
            logging.info("show_preview(): Stopped Preview")
            return


def config_camera():
    """
    Name: config_camera()
    Author: robertdcurrier@gmail.com
    Created: 2021-05-02
    Modified: 2022-02-15
    Notes: Now working with taxa-specific settings
    """
    global CAMERA
    try:
        CAMERA = PiCamera()
    except:
        logging.warning('config_camera(): Failed to open PiCamera!')
        sys.exit()

    config = get_sql_config('configuration')
    taxa = config['taxa']
    camera_config = get_sql_config(taxa)
    # Get crop size params and convert to list of ints
    x1,y1,x2,y2 = camera_config["camera_preview_size"].split(',')
    crop_size = float(x1),float(y1),float(x2),float(y2)
    record_width = int(config["record_width"])
    record_height = int(config["record_height"])
    CAMERA.zoom = (crop_size)
    CAMERA.contrast = int(camera_config["camera_contrast"])
    CAMERA.sharpness = int(camera_config["camera_sharpness"])
    CAMERA.brightness = int(camera_config["camera_brightness"])
    CAMERA.saturation = int(camera_config["camera_saturation"])
    CAMERA.exposure_mode = camera_config["camera_exposure_mode"]
    CAMERA.meter_mode = camera_config["camera_meter_mode"]
    CAMERA.exposure_compensation = int(camera_config["camera_ev"])
    CAMERA.resolution=(record_width, record_height)



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
    dts = date.today().strftime('%Y-%m-%d')
    logfile = '/data/logs/%s.log' % dts
    logging.basicConfig(filename=logfile, level=logging.INFO,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y/%m/%d %I:%M:%S %p')
    logging.info("config_logger(): Succesfully configured logging...")


def system_update():
    """
    Name: system_update()
    Author: robertdcurrier@gmail.com
    Created: 2021-07-12
    Modified: 2022-03-29
    Notes: scp from server to get latest version

    """
    config = get_sql_config('configuration')
    from_path = "/data/habscope2/updates/habscope_dist/*"
    out_path = "/home/pi/habscope"
    server = config["server"]
    pw = config['pw']
    userid = config['userid']
    command = "sshpass -p %s rsync -ae 'ssh -p 22' %s://%s %s" % (pw, server, from_path, out_path)
    msg = "system_update(): Getting latest code..."
    logging.info(msg)
    try:
        os.system(command)
        msg = "system_update(): Update succeeded."
        logging.info(msg)
        return True
    except:
        msg = "system_update(): Update failed."
        logging.info(msg)
        return False

def show_progress(filename, size, sent):
    """ do what it say """
    global d
    percentage = int(float(sent)/float(size)*100)
    d.gauge_update(percentage)


def create_connection(dbfile):
    """ create a database connection to the SQLite database """
    logging.info("create_connection(): Opening connection to configuration DB")
    conn = None
    try:
        conn = sqlite3.connect(dbfile)
    except Error as e:
        logging.warning(e)
    return conn


def get_results(anal_path):
    """
    Name: get_results()
    Author: robertdcurrier@gmail.com
    Created: 2021-07-19
    Modified: 2022-02-03 got progress gauge working
    Notes:
    """
    logging.info('get_results()')
    config = get_sql_config('configuration')
    userid = config['userid']
    pw = config['pw']
    server = config['server']
    upload_timeout=int(config["upload_timeout"])
    msg = "get_results(): Creating ssh client"
    logging.warning(msg)
    ssh = SSHClient()
    start_time = int(time.time())
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    msg = 'get_results(): Set Missing Host Key okay...'
    logging.info(msg)
    ssh.connect(server,username=userid, password=pw)
    msg = 'get_results(): Connected to server okay'
    logging.info(msg)
    start_time = int(time.time())
    msg = 'get_results(): Using %s' % anal_path
    logging.debug(msg)
    (root_path, processed_image) = os.path.split(anal_path)
    processed_image = processed_image.replace('raw','pro')
    msg = 'root_path: %s, processed_image: %s' % (root_path, processed_image)
    logging.debug(msg)
    save_file = '/data/images/%s' % processed_image
    msg = 'get_results(): save_file is %s' % save_file
    logging.debug(msg)
    try:
        with SCPClient(ssh.get_transport(),progress=show_progress) as scp:
            scp.get(anal_path, save_file)
            return save_file
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

    logging.info("get_sql_config(%s): Get config values from config.db" % table)
    conn = create_connection('./config.db')
    cur = conn.cursor()
    configs = {}
    try:
        results = cur.execute('SELECT * from %s' % table)
    except Error as e:
        logging.warning(e)
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
    try:
        _ = requests.head(url, timeout=timeout)
        logging.info("connected_to_internet(): True")
        return True
    except requests.ConnectionError:
        logging.info("connected_to_internet(): False")
        return False


def rsync_logs():
    """
    Name: rsync_logs()
    Author: robertdcurrier@gmail.com
    Created: 2021-07-12
    Modified: 2022-03-17
    Notes: rsyncs logs to habscope2.gcoos.org for diags

    """
    config = get_sql_config('configuration')
    serial = config["serial"]
    logdir = "/data/logs/*"
    outdir = "/data/habscope2/logs/%s" % serial
    server = config["server"]
    pw = config['pw']
    userid = config['userid']
    command = "sshpass -p %s rsync -ae 'ssh -p 22' /data/logs/*.log  " % (pw)
    command = command + "%s@%s:/data/habscope2/logs/%s" % (userid, server, serial)
    msg = "rsync_logs(): Syncing logfiles"
    logging.info(msg)
    try:
        os.system(command)
        msg = "rsync_logs(): Logfile sync succeeded."
        logging.info(msg)
    except:
        msg = "rsync_logs(): Logfile sync failed."
        logging.info(msg)


"""
BEGIN STATE COUNTY SITE MENU SYSTEM
"""
def add_new_site():
    """
    2022-08-26
    Allows user to add new site to list. Writes to custom_sites.db
    """
    return


def get_states(cur):
    """
    Fetch all unique states
    """
    choices = []
    states = []
    sql_text = """select distinct state from sites ORDER BY state ASC"""
    try:
       results = cur.execute(sql_text)
    except Error as e:
       logging.warning(e)
       sys.exit()
    finally:
        rows = cur.fetchall()
        # Populate the table
        for row in rows:
            (state) = row
            record = "%s" % (state)
            choices.append(record)
            choices.append("")
    (code, state) = d.menu("", 10, 30, 20,
            choices=[(choices)], title="Select State")
    if code == 'ok':
        return state
    else:
        lat_lon_menu()


def get_counties(cur, state):
    """
    Fetch all unique counties
    """
    choices = []
    counties = []
    sql_text = """select distinct county from sites where state = '%s'
    ORDER BY county ASC""" % state
    try:
       results = cur.execute(sql_text)
    except ValueError as e:
        logging.warning("get_counties(): %s", e)
        sys.exit()
    finally:
        rows = cur.fetchall()
        menu_l = len(rows)+2
        menu_h = menu_l+5
        # Populate the table
        for row in rows:
            (county) = row
            record = "%s" % (county[0])
            choices.append(record)
            choices.append("")
    (code, county) = d.menu("", menu_h, 30, menu_l,
            choices=[(choices)], title="Select County")
    if code == 'ok':
        return county
    else:
        lat_lon_menu()


def get_sites(cur, state, county):
    """
    Fetch all sites in a county
    """
    sites = []
    sql_text = ("""select * from sites where state='%s' and
            county='%s' ORDER BY site ASC""" %
                (state, county))
    try:
       results = cur.execute(sql_text)
    except ValueError as e:
       logging.warning("get_sites() %s", e)
       sys.exit()
    finally:
        rows = cur.fetchall()
        for row in rows:
            sites.append(row)
    return sites



def lat_lon_menu():
    """
    2022-08-26
    """
    choices = []
    conn = create_connection('./config.db')
    cur = conn.cursor()
    state = get_states(cur)
    county = get_counties(cur, state)
    sql_text = """SELECT * FROM sites where state = '%s' and county = '%s'
    ORDER by SITE ASC""" % (state, county)
    sites = cur.execute(sql_text)
    try:
       results = cur.execute(sql_text)
    except ValueError as e:
       logging.warning(e)
       sys.exit()
    finally:
        rows = cur.fetchall()
        menu_l = len(rows)+2
        menu_h = menu_l+5
        # Populate the table
        for row in rows:
            (country, state, county, site, lat, lon) = row
            choices.append(site)
            choices.append("")

    (code, site) = d.menu("",menu_h, 40, menu_l,
            choices=[(choices)], title="Select Site",
            help_tags=True)
    if code == 'ok':
        # query from sqlite instead of trying to deal with wonky
        # dialog menu system -- should be much easier
        (lat, lon) = get_coords(cur, country,state,county,site)
        return(lat, lon, site)
    else:
        lat_lon_menu()


def get_coords(cur, country, state, county, site):
    """
    Gets lat/lon from sites table. Dialog unable to return
    both menu columns data so we have to do a lookup based
    on site.
    """
    sql_text = """select lat, lon from sites where country = '%s' and
    state = '%s' and county = '%s' and site = '%s'""" % (country, state,
                                                         county, site)
    try:
        results = cur.execute(sql_text)
        row = cur.fetchall()[0]
        (lat, lon) = row
        return (lat, lon)

    except ValueError as e:
        logging.warning('get_coords(): %s', e)
        sys.exit()

"""
END STATE COUNTY SITE MENU SYSTEM
"""

def hsp_cli():
    """
    Name: hsp_cli
    Author: robertdcurrier@gmail.com
    Created: 2021-07-01
    Modified: 2021-07-07
    Notes:
    Now using Dialog for menuing. pydialog, actually...

    """
    config_logger()
    logging.info("HABscope 2.0 GUI Starting Up...")
    check_serial()
    config_camera()
    main_menu()


if __name__ == '__main__':
    os.system('clear')
    hsp_cli()
