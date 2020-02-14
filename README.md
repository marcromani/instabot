# instabot
## Simple, easy-to-use Instagram bot

### Requirements
* `python >= 3.7`
* `pip install selenium`

### Usage
Running the bot is easy. First, configure it:
```
python instabot.py config -u USERNAME -p PASSWORD
```
This is the simplest case, where all the configuration parameters are left as default. A much verbose case looks like this:
```
python instabot.py config -u USERNAME -p PASSWORD -t TAGS_FILE -c COMMENTS_FILE -i FOLLOW_UNFOLLOW_INTERVAL -s SLEEP_TIME
```
There are even other options, issue the help (-h) option to gather more information. In all cases, the `config` command saves the configuration parameters in a hidden file inside the data folder.

Once the bot is configured you can follow new users with:
```
python instabot.py follow -n NUM_USERS
```
And you can unfollow them with:
```
python instabot.py unfollow -m MAX_USERS
```
Again, more parameters can be provided to both commands, check the documentation for all the available options and their meaning.
