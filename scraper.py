import json
import logging
import argparse
import sys
import time
from scrapers.config import beanstalk, db_insert
from publications import scrapermap
from requests.exceptions import ConnectionError
import settings

logger = logging.getLogger(__name__)

def consumer():
    logger.info("Starting consumer")
    while True:
        logger.info("Waiting for job")
        job = beanstalk.reserve()
        scrape_job = json.loads(job.body)
        logger.info("Job payload: %s" % scrape_job)
        scraper_name = scrape_job["scraper"]
        scraper = scrapermap[scraper_name]
        post = scraper.consume(scrape_job)
        if post:
            entry = post.get("text", "").strip()
            if len(entry) < 5:
                logger.warn("Missing text from %s" % post["url"])
            db_insert(post)
        job.delete()

def producer():
    for publication, scraper in scrapermap.items():
        try:
            logger.info("Producer is running: %s" % publication)
            for job in scraper.produce():
                if job:
                    beanstalk.put(job)

        except ConnectionError:
            logger.exception("Could not connect to server for %s" % publication)
        except Exception:
            logger.exception("Error occurred in producer for %s" % publication)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("task", help="Select either producer, consumer or twitter. Producers collect urls and place them in a queue. Consumers scrape those urls. Twitter will run the twitter stream api and collect tweets")
    args = parser.parse_args()

    if args.task == "consumer":
        consumer()
    elif args.task == "producer":
        producer()
    elif args.task == "twitter":
        from scrapers.twitter import twitter
        twitter.run(
            settings.consumer_key, settings.consumer_secret, settings.access_token, settings.access_token_secret
        )
    else:
        # TODO - figure out how to throw an argparse error
        print "Invalid option"
        sys.exit()
