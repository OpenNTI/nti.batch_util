import argparse
import codecs
import csv


def parse_args():
    arg_parser = argparse.ArgumentParser(description="Generate scripts to create analytic db")
    arg_parser.add_argument('csv',
                            help="CSV file location. It should have a column header named 'AnalyticsDB'.")
    arg_parser.add_argument('-s', '--script',
                            help="Filename to save the db creation script",
                            default='analytics_db.sql')
    return arg_parser.parse_args()


def generate_script(db_names):
    scripts = []
    for db_name in db_names:
        template = """CREATE DATABASE {};
        GRANT ALL ON {}.* TO 'ntianalytics'@'10.50.0.0/255.255.0.0';
        GRANT ALL ON {}.* TO 'backup'@'10.50.0.0/255.255.0.0';""".format(db_name, db_name, db_name)
        scripts.append(template)
    template = """
    GRANT REPLICATION SLAVE ON *.* TO 'backup'@'10.50.0.0/255.255.0.0';
    GRANT RELOAD ON *.* TO 'backup'@'10.50.0.0/255.255.0.0';
    GRANT REPLICATION CLIENT ON *.* TO 'backup'@'10.50.0.0/255.255.0.0';
    FLUSH PRIVILEGES;"""
    scripts.append(template)
    result = u'\n\n'.join(scripts)
    result = result.replace(u'        ', u'')
    return result


def read_csv(filename):
    db_names = []
    with open(filename, mode='r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        for row in csv_reader:
            db_names.append(row['AnalyticsDB'])
    return db_names


def main():
    args = parse_args()
    db_names = read_csv(args.csv)
    scripts = generate_script(db_names)
    with codecs.open(args.script, "w") as fp:
        fp.write(scripts)


if __name__ == '__main__':  # pragma: no cover
    main()
