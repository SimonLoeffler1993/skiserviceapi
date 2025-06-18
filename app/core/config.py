
class DbSettings:
    host = "192.168.188.10"
    port = 3306
    user = "root"
    password = "SimonRoot"
    database = "skiservice_dev"
    mysql_constring = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"


dbSettings = DbSettings()
