#!/usr/bin/env python3
"""
2022-08-26
Test of the lat/lon retained position list and menu autopopulate
code. We need to get the lat/lon entry down to a single dialog panel,
and retain the entered positions in a json text file. If working properly,
the code will pull the most recently entered position from the list and
autopopulate the lat/lon boxes in the dialog. An ordered list of all positions
should be displayed, allowing the user to scroll down and choose another site.
That site will then become the default.

Update 2022-08-29: Moved to sqlite3 table for all sites. That way we can sort by
country, state and county. Custom sites will be stored in custom_sites.db so we
don't overwrite when doing a systems update.
"""
import os
import sys
import logging
import json
import sqlite3
from dialog import Dialog


def create_connection(dbfile):
    """ create a database connection to the SQLite database """
    logging.info("create_connection(): Opening connection to configuration DB")
    conn = None
    try:
        conn = sqlite3.connect(dbfile)
    except Error as e:
        logging.warning(e)
    return conn


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

    (code, site) = d.menu("",menu_h, 60, menu_l,
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

if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=logging.INFO)
    d = Dialog(dialog="dialog")
    (lat, lon, site) = lat_lon_menu()
    print(lat, lon, site)
