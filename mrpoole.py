from sh import git, jekyll, service, sh, sudo
import requests
import re
import os
from requests.auth import HTTPBasicAuth
from jinja2 import Template
import sqlite3
import logging
import json

SITES_DIR = '/var/www/html'
ORGANIZATION = 'jjwebstuff'
REPOS_DIR = '/home/ubuntu/repos'
DBPATH = '/home/ubuntu/mrpoole.db'
WEB_CONFIG_DIR = '/home/ubuntu/'
FORMAT = "%(asctime)s %(levelname)s %(module)s %(message)s"
logging.basicConfig(format=FORMAT,)
logger = logging.getLogger('mrpoole')
logger.setLevel(logging.INFO)


def get_repos(organization):
  repo_list = []
  r = requests.get('https://api.github.com/orgs/%s/repos' % organization)
  for repo in r.json():
    repo_name = repo['name']
    repo_list.append('https://github.com/jjwebstuff/{}.git'.format(repo_name))
  return repo_list

def get_raw_sha(sha):
  value = re.search('[a-zA-Z0-9]{40}',str(sha))
  return value.group(0)

def create_directory(site_name):
  SITE_PATH = '{}/{}'.format(SITES_DIR, site_name)
  if not os.path.exists(SITE_PATH):
    os.makedirs(SITE_PATH)
  return True

def create_vhost(repo_url):
  source = "%s/vhost.json" % source_path(repo_url)
  try:
    f = open(source)
    data = json.load(f)
    site_name = data['site']
    aliases = data['aliases']
    name = name_from_url(repo_url)
    SITE_FILE='/etc/apache2/sites-available/30_{}.conf'.format(name)
    if not os.path.exists(SITE_FILE):
      temp_file = open('/home/ubuntu/mrpoole/vhost.jinja')
      template = Template(temp_file.read())
      vhost = template.render(site=site_name, aliases=aliases, name=name)
      with open( SITE_FILE, 'w') as f:
        f.write(vhost)
      os.symlink(SITE_FILE, '/etc/apache2/sites-enabled/30_{}.conf'.format(name))
      logger.info("Successfully created {}".format(SITE_FILE))
  except Exception as ex:
    msg = "Failed when creating the vhost for {}".format(repo_url)
    logging.error(msg)
    logging.exception(ex)
  
def install_site(repo_url):
  source = source_path(repo_url)
  destination = destination_path(repo_url)
  try:
    os.chdir(source)
    jekyll.build('--destination', destination)
    commit_sha = git.log("-n1", "--pretty='%H'")
    logging.info("Installed site from {}".format(repo_url))
    return get_raw_sha(commit_sha)
  except Exception as ex:
    logging.error("Failed to build the Jekyll file. Exception follows")
    logging.exception(ex)
    return None

def get_last_processed_commit(repo_url):
  cursor = get_db()
  url = (repo_url,)
  result = cursor.execute('SELECT commitnumber from repos where repo_url = ?', url)
  row = result.fetchone()
  return row[0]

def get_current_commit(repo_url):
  source = source_path(repo_url)
  os.chdir('{}'.format(source))
  git.pull('origin', 'master')
  commit_sha = git.log("-n1", "--pretty='%H'")
  return get_raw_sha(commit_sha)

def get_db():
  connection = sqlite3.connect(DBPATH)
  return connection


def update_commit(repo_url, commit_sha):
  connection = get_db()
  cursor = connection.cursor()
  previous_commit = get_last_processed_commit(repo_url)
  if not previous_commit:
    QUERY = 'INSERT INTO repos (commitnumber, repo_url) VALUES (?, ?)'
    VALUES = (commit_sha, repo_url)
  else:
    QUERY = 'UPDATE repos set commitnumber = ? where repo_url = ?'
    VALUES = (commit_sha, repo_url)
  cursor.execute(QUERY, VALUES)
  connection.commit()

def name_from_url(repo_url):
  repo =  repo_url.rsplit('/', 1)
  return repo[1].replace('.git','')

def is_deployed(repo_url):
  connection = get_db()
  cursor = connection.cursor()
  QUERY = 'SELECT repo_url FROM repos where repo_url = ?'
  VALUES = (repo_url,)
  result = cursor.execute(QUERY, VALUES)
  rows = result.fetchall()
  if len(rows) > 0 :
    return True
  else:
    return False

def destination_path(repo_url):
  repo = name_from_url(repo_url)
  return '%s/%s' % (SITES_DIR, repo)

def source_path(repo_url):
  repo = name_from_url(repo_url)
  return '%s/%s' % (REPOS_DIR, repo)

def initial_deploy(repo_url):

  os.chdir('%s' % REPOS_DIR)
  git.clone(repo_url)
  dest = destination_path(repo_url)
  if not os.path.exists(dest):
    os.makedirs(dest)
  commit_sha = install_site(repo_url)
  if commit_sha:
    update_commit(repo_url, commit_sha)
    installOK = True
  else:
    logger.error("Failed to install repo %s on initial deploy" %s)
    installOK = False 
  return installOK
  
def main():
  repos = get_repos(ORGANIZATION)
  apache_needs_restart = False
  for repo in repos:
    try:
      logger.info("Processing repo %s" % repo)
      if not is_deployed(repo):
        logger.info("Found new repo at %s" % repo)
        initial_deploy(repo)  
        create_vhost(repo)
      else:
        commit = get_last_processed_commit(repo)
        current_commit = get_current_commit(repo)  
        if current_commit != commit:
          logger.info("Found new commit in %s" % repo)
          commit = install_site(repo) 
          create_vhost(repo)
          update_commit(repo, current_commit)
        else:
          logger.info("No changes detected for {}".format(repo))
      apache_needs_restart = True
    except Exception as ex:
      logging.error("Failed to update repo.")
      logging.exception(ex)

  if apache_needs_restart:
    logger.info("Restarting Apache gracefully")
    sudo.service("apache2", "graceful")   
     
if __name__ == '__main__':
  logger.info("Beginning repo fetch")
  main()
	
