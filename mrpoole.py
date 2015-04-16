from sh import git, jekyll, service
import requests
import os
from requests.auth import HTTPBasicAuth
from jinja2 import Template
import sqlite3

SITES_DIR = '/var/www/html'
ORGANIZATION = 'jjwebstuff'
REPOS_DIR = '/home/ubuntu/repos'



def get_repos(organization):
  repo_list = []
  r = requests.get('https://api.grubhub.com/org/%s/repos' % organization)
  for repo in r.json():
    repo_list.append(repo['url'])
  return repo_list


def create_directory(site_name):

  SITE_PATH = '%s/%s' % SITES_DIR, site_name)
  if not os.path.exists(SITE_PATH):
    os.makedirs(SITE_PATH)
  return True

def create_vhost(site_name):

  SITE_FILE='%s/%s/30_%s.conf')
  temp_file = open('vhost.jinja')
  template = Template(temp_file.read())
  vhost = template.render(site=site_name)
  with open('%s' % SITE_FILE) as f:
    f.write(vhost)
  
def install_site(source, destination):
  try:
    os.chdir(source)
    jekyll.build('--destination', destination)
    service.graceful("apache2")   
    commit_sha = git.log("-n1", "--pretty='%H'")
    return commit_sha
  except:
    return None

def get_last_processed_commit(repo_url):
  cursor = get_db()
  url = (repo_url,)
  result = cursor.execute('SELECT commitnumber from repos where repo_url = ?', url)
  return result.fetchone()

def get_current_commit(repo_url):
  folder = name_from_url(repo_url)
  os.chdir('%s/%s' % (REPO_DIR, folder))
  git.pull('origin', 'master')
  commit_sha = git.log("-n1", "--pretty='%H'")
  return commit_sha

def get_db():
  connection = sqlite3.connect('mrpoole.db')
  cursor = connection.cursor()
  return cursor


def update_commit(repo_url, commit_sha):

  cursor = get_db()
  previous_commit = get_last_commit(repo_url)
  if not previous_commit:
    QUERY = 'INSERT INTO repos VALUES (?, ?)'
    VALUES = (repo_url, commit_sha)
  else:
    QUERY = 'UPDATE repos set commitnumber = ? where repo_url = ?'
    VALUES = (commit_sha, repo_url)
  result = cursor.execute(QUERY, VALUES)

def name_from_url(repo_url):
  return repo_url.rsplit('/', 1)

def is_deployed(repo_url):
  cursor = get_db()
  QUERY = 'SELECT repo_url FROM repos where repo_url = ?'
  VALUES = (repo_url)
  result = cursor.execute(QUERY, VALUES)
  if result.rowcount() > 0 :
    return True
  else:
    return False

def destination_path(repo_url):
  repo = name_from_url(repo_url)
  return '%s/%s' % (SITES_DIR, repo)

def initial_deploy(repo_url):

  os.chdir('%s' % REPO_DIR)
  git.clone(repo_url)
  commit_sha = install_site(os.getcwd, destination_path(repo_url))
  if commit_sha:
    update_commit(repo_url, commit_sha)
    installOK = True
  else:
    print "Problem installing site %s" % repo_url
    installOK = False 

  return installOK
  
def main():
  repos = get_repos(ORGANIZATION)
  for repo in repos:
    if not is_deployed(repo):
      initial_deploy(repo)  
    else:
      commit = get_last_processed_commit(repo_url)
      current_commit = get_current_commit(repo_url)  
     
