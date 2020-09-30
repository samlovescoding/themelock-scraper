import requests
from bs4 import BeautifulSoup
import pymongo
import os
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import as_completed

# Globals
client = pymongo.MongoClient("localhost", 27017)
db = client.themelock
MAX_CPU_WORKERS = 120

# Utility Functions
def source(url):
  log(url, "down")
  return requests.get(url).text

def soup(url):
  return BeautifulSoup(source(url), "html.parser")

def log(message, type = "info"):
  print("[{}] {}".format(type, message))

def download_file(url, folder):
  if not os.path.exists(folder):
    os.mkdir(folder)
  local_filename = folder + "/" +url.split('/')[-1]
  with requests.get(url, stream=True) as r:
    r.raise_for_status()
    with open(local_filename, 'wb') as f:
      for chunk in r.iter_content(chunk_size=8192):
        f.write(chunk)
  return local_filename

# Single Function
def save_single(title, tags, demo, links, screenshot, description):
  db.singles.insert_one({
    "title": title,
    "tags": tags,
    "demo": demo,
    "links": links,
    "screenshot": screenshot,
    "description": description
  })

def download_single(url):
  src = soup(url)

  title = ""
  tags = []
  demo = ""
  links = []
  screenshot = ""
  description = ""

  # Title
  title = src.find("h1", {"class": "entry-titles"}).text

  # Tags
  div = src.find("div", {"class": "categ"})
  for a in div.findAll("a"):
    tags.append(a.text)

  # Demo
  demo = src.find("div", {"class": "descripton"}).find("a").text

  # Links
  links = src.find("div", {"class": "descripton"}).find("div", {"class": "quote"}).get_text(separator="\n").split("\n")

  # Screenshot
  screenshot = src.find("div", {"class": "full-news type img"}).find("img").get("src")

  # Description
  description = src.find("div", {"class": "descripton"}).get_text(separator="\n").split("Demo:")[0].replace("\n", " ").strip()

  save_single(title, tags,  demo, links, screenshot, description)

def download_single_multi(template_url):
  download_single(template_url['url'])
  db.template_urls.update_one({
    "_id": template_url["_id"]
  }, {
    "$set": {
      "isDownloaded": True
    }
  })

# List Functions

def save_list(sublist):
  #db.template_urls.insert_many(sublist)
  for item in sublist:
    records = db.template_urls.count_documents({"title": item["title"]})
    if records == 0:
      db.template_urls.insert_one(item)

def download_list(page):
  url = "https://www.themelock.com/page/{}/".format(page)
  src = soup(url)

  sublist = []
  for newTitle in src.findAll("div", {"class": "news-titles"}):
    sublist.append({
      "title": newTitle.find("a").get("title"),
      "url": newTitle.find("a").get("href"),
      "isDownloaded": False
    })
  save_list(sublist)
  return sublist

# Multiprocessing Functions

def multiprocess(fn, data):
  with ProcessPoolExecutor(max_workers = MAX_CPU_WORKERS) as executor:
    results = executor.map(fn, data)

# Website Download Function

def download_website():

    # Download Lists
    url = "https://www.themelock.com/"
    src = soup(url)
    max_pages = int(src.find("ul", {"class": "pagination"}).findAll("li")[1].findAll("a")[-1].text)
    for i in range(1, max_pages + 1):
      download_list(i)

    # Download Singles
    for template_url in db.template_urls.find({
      "isDownloaded": False
    }):
      download_single(template_url['url'])
      db.template_urls.update_one({
        "_id": template_url["_id"]
      }, {
        "$set": {
          "isDownloaded": True
        }
      })

def download_website_with_singles():
    # Download Lists
    url = "https://www.themelock.com/"
    src = soup(url)
    max_pages = int(src.find("ul", {"class": "pagination"}).findAll("li")[1].findAll("a")[-1].text)
    for i in range(1, max_pages + 1):
      download_list(i)

      for template_url in db.template_urls.find({
        "isDownloaded": False
      }):
        download_single(template_url['url'])
        db.template_urls.update_one({
          "_id": template_url["_id"]
        }, {
          "$set": {
            "isDownloaded": True
          }
        })

def download_website_multi():
  # Download Lists
  url = "https://www.themelock.com/"
  src = soup(url)
  max_pages = int(src.find("ul", {"class": "pagination"}).findAll("li")[1].findAll("a")[-1].text)
  list_set = list(range(1, max_pages + 1))
  multiprocess(download_list, list_set)

  # Download Singles
  template_url_set = db.template_urls.find({
    "isDownloaded": False
  })
  multiprocess(download_single_multi, template_url_set)

# Main Function
def main():
  download_website_multi()

if __name__ == "__main__":
  main()
