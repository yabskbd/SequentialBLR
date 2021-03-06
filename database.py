# Filename:     database.py
# Author:       Adrian Padin
# Start Date:   5/25/2016

import mysql.connector
import datetime as dt

class Database:

    # Constructor
    # Reads config file and connects to database
    def __init__(self):
        
        with open('config.txt') as file:
            for line in file:
                if line.startswith('HOST'):
                    loc = line.find('=')
                    hst = line[loc+1:].rstrip()
                elif line.startswith('DATABASE'):
                    loc = line.find('=')
                    db = line[loc+1:].rstrip()
                elif line.startswith('USER'):
                    loc = line.find('=')
                    usr = line[loc+1:].rstrip()
                elif line.startswith('PASSWORD'):
                    loc = line.find('=')
                    pswd = line[loc+1:].rstrip()
                    
        config = {
            'user': usr,
            'password': pswd,
            'host': hst,
            'database': db,
            'raise_on_warnings': True
        }

        print "Connecting to database..."        
        self.cnx = mysql.connector.connect(**config)
        self.cursor = self.cnx.cursor()

    # Execute an arbitrary SQL command
    def execute(self, command):
        self.cursor.execute(command)
        return self.cursor.next()

    # Return a list of the data averaged over the specified period
    # columns is a list of columns names to query for
    # start_time and end_time must be datetime objects of the same type
    def get_avg_data(self, start_time, end_time, columns):
        
        if (start_time > end_time):
            raise ValueError("end_time must come after start_time")

        #Build the query:
        isFirst = True
        qry = "SELECT "
        for name in columns:
            if not isFirst:
                qry += ", "
            else:
                isFirst = False

            if "motion" in name:
                qry = qry + "SUM(" + name + ")"
            else:
                qry = qry + "AVG(" + name + ")"

        qry = qry + " FROM SMART WHERE dataTime BETWEEN %s AND %s"

        # Execute the query and return the results
        self.cursor.execute(qry , (start_time, end_time))
        return self.cursor.next()
        
        
    # Destructor
    # Close the connection when the Database goes out of scope
    def __del__(self):
        self.cursor.close()
        self.cnx.close()
