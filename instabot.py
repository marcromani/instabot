#!/usr/bin/env python

import argparse
import json
import os
from datetime import datetime
from random import shuffle
from time import sleep
from warnings import warn

from selenium import webdriver


class InstaBotDB:
    def __init__(self, path='./data/.instabot_db'):
        self._path = path

        if not os.path.exists(path):
            data = {
                'users': [],
                'likes': [],
                'comments': []
            }

            with open(path, 'w') as f:
                json.dump(data, f)

        with open(path) as f:
            self._data = json.load(f)

    def add_user(self, username, days_to_wait):
        """
        Add a new user to the followed list.

        Once a user is added to the list it persists there even if it
        is unfollowed. Only when `days_to_wait` days have passed it is
        marked as available and can be followed again (or eventually be
        removed from the list). It is assumed that this function is called
        over an unfollowed user, consequently, if the user appears in the
        database as followed it is marked as unfollowed. This could happen
        if a user was manually unfollowed.

        """
        users = self._data['users']

        # User not in the database, create a new entry for it
        if username not in [u['username'] for u in users]:
            self._data['users'].append({
                'username': username,
                'date_followed': datetime.now().strftime('%Y/%m/%d')
            })
            result = True

        else:
            idx, user = [
                (i, u) for i, u in enumerate(users)
                if u['username'] == username
            ][0]

            # User already in the database as followed, mark as unfollowed
            if 'date_followed' in user:
                user.pop('date_followed')
                user['date_unfollowed'] = datetime.now().strftime('%Y/%m/%d')
                self._data['users'][idx] = user
                result = False
            # User already in the database as unfollowed, mark as followed (if possible)
            else:
                date_unfollowed = user['date_unfollowed']
                now = datetime.now().strftime('%Y/%m/%d')
                if InstaBotDB._days_interval(date_unfollowed, now) >= days_to_wait:
                    user.pop('date_unfollowed')
                    user['date_followed'] = now
                    self._data['users'][idx] = user
                    result = True
                else:
                    result = False

        with open(self._path, 'w') as f:
            json.dump(self._data, f)

        return result

    def remove_user(self, username):
        pass

    def user_exists(self, username):
        pass

    @staticmethod
    def _days_interval(date1, date2):
        d1 = datetime.strptime(date1, '%Y/%m/%d')
        d2 = datetime.strptime(date2, '%Y/%m/%d')
        return abs((d2 - d1).days)


class InstaBot:
    def __init__(self, chrome_driver='./data/chromedriver', sleep_time=3):
        self._web = webdriver.Chrome(
            executable_path=chrome_driver
        )

        self.sleep_time = sleep_time

    def login(self, username, password, days_to_wait=15, tags=[], comments=[], database='./data/.instabot_db'):
        self._username = username
        self._days_to_wait = days_to_wait
        self._tags = tags
        self._comments = comments
        self._db = InstaBotDB(database)

        self._web.get('https://www.instagram.com/accounts/login/')
        sleep(self.sleep_time)

        username_box = self._web.find_element_by_name('username')
        password_box = self._web.find_element_by_name('password')
        login_button = self._web.find_element_by_css_selector(
            '#react-root > section > main > div > article > div > div:nth-child(1) > div > form > div:nth-child(4) > button'
        )

        username_box.send_keys(username)
        password_box.send_keys(password)
        login_button.click()
        sleep(self.sleep_time)

        try:
            notnow = self._web.find_element_by_css_selector(
                'body > div.RnEpo.Yx5HN > div > div > div.mt3GC > button.aOOlW.HoLwm'
            )
            notnow.click()
        except Exception:
            pass

    def follow(self, num_users, comment_prob=0.1, days_to_wait=None, tags=[], comments=[]):
        """Follow `num_users` new users.

        Find posts tagged with keywords in `tags` which belong to users not currently
        followed. Like and comment them (with probability `comment_prob`, using comment
        sentences in `comments`), and follow their authors. This will only happen for
        users which have been unfollowed by at least `days_to_wait` days.

        """
        if days_to_wait is None:
            days_to_wait = self._days_to_wait

        if not tags:
            tags = self._tags

        if not tags:
            warn('Target hashtags should be provided!')
            return

        if num_users >= len(tags):
            users_per_tag = num_users // len(tags)
        else:
            users_per_tag = len(tags)

        posts_per_tag = 2 * users_per_tag
        posts_per_page = 10

        # Collect posts for the specified tags
        posts = []

        for tag in tags:
            self._web.get(f'https://www.instagram.com/explore/tags/{tag}/')
            sleep(self.sleep_time)

            pages_per_tag = posts_per_tag // posts_per_page + 1
            posts += self._scroll_down(pages_per_tag)

        shuffle(posts)
        posts = set(posts)

        # Follow users
        new_users = 0

        while new_users < num_users:
            if not posts:
                break

            url = posts.pop()

            self._web.get(url)
            sleep(self.sleep_time)

            username = self._web.find_element_by_css_selector(
                '#react-root > section > main > div > div > article > header > div.o-MQd.z8cbW > div.PQo_0.RqtMr > div.e1e1d > h2 > a'
            ).text

            follow_button = self._web.find_element_by_css_selector(
                '#react-root > section > main > div > div > article > header > div.o-MQd.z8cbW > div.PQo_0.RqtMr > div.bY2yH > button'
            )

            # Button displays 'Follow' so we are not following this user
            if follow_button.text == 'Follow':
                # User could be effectively (re-)followed
                if self._db.add_user(username, days_to_wait):
                    like_button = self._web.find_element_by_css_selector(
                        '#react-root > section > main > div > div > article > div.eo2As > section.ltpMr.Slqrh > span.fr66n > button'
                    )

                    like_button.click()
                    sleep(self.sleep_time)

                    follow_button.click()
                    sleep(self.sleep_time)

                    new_users += 1

        print(f'Following {new_users}/{num_users} new users')

    def unfollow(self, max_users, days_to_wait=None):
        """
        Unfollow (at most) `max_users` users.

        Go over the list of followed users who have been followed for at least
        `days_to_wait` days and unfollow (at most) `max_users` of them.

        """
        if days_to_wait is None:
            days_to_wait = self._days_to_wait

        # Get all followed users which could be unfollowed
        now = datetime.now().strftime('%Y/%m/%d')

        following = [u for u in self._db._data['users'] if 'date_followed' in u]
        following = [
            u for u in following
            if InstaBotDB._days_interval(u['date_followed'], now) >= days_to_wait
        ]
        following = [u['username'] for u in following]

        if not following:
            print(f'Unfollowed 0/{max_users} users')
            return

        # Get all followers
        self._web.get(f'https://www.instagram.com/{self._username}/')
        sleep(self.sleep_time)

        self._web.find_element_by_partial_link_text('followers').click()
        sleep(self.sleep_time)

        followers_list = self._web.find_element_by_css_selector(
            'body > div.RnEpo.Yx5HN > div > div.isgrP'
        )

        last_height = self._web.execute_script('''
            return document.querySelector('div[role="dialog"] .isgrP').scrollHeight
        ''')

        followers = []

        while True:
            _followers = followers_list.find_elements_by_xpath('.//a[@href]')
            followers += [
                u.get_attribute('href').split('/')[-2]
                for u in _followers
            ]

            self._web.execute_script('''
                var fDialog = document.querySelector('div[role="dialog"] .isgrP');
                fDialog.scrollTop = fDialog.scrollHeight
            ''')
            sleep(self.sleep_time)

            new_height = self._web.execute_script('''
                return document.querySelector('div[role="dialog"] .isgrP').scrollHeight
            ''')

            if new_height == last_height:
                break

            last_height = new_height

        # Divide the people we follow in two groups:
        # The good: People that follow us back.
        # The bad: People that do not follow us back.
        good = set(following).intersection(set(followers))
        bad = set(following) - good

        # Iterate through this list until `max_users` are unfollowed or
        # the list ends. First unfollow the good (!) users, then the bad ones.
        users_to_unfollow = list(good) + list(bad)

        deleted_users = 0

        while deleted_users < max_users and users_to_unfollow:
            u = users_to_unfollow.pop(0)

            self._web.get(f'https://www.instagram.com/{u}/')
            sleep(self.sleep_time)

            follow_button = self._web.find_element_by_css_selector('button')

            if follow_button.text == 'Following':
                follow_button.click()
                sleep(self.sleep_time)

                self._web.find_element_by_xpath(
                    '//button[text()="Unfollow"]'
                ).click()
                sleep(self.sleep_time)

                deleted_users += 1
            else:
                # We are not actually following this user, which means
                # that we manually unfollowed him at some point. Update
                # the database only.
                pass

            # Set the user as unfollowed in the database
            idx, user = [
                (i, usr) for i, usr in enumerate(self._db._data['users'])
                if usr['username'] == u
            ][0]

            user.pop('date_followed')
            user['date_unfollowed'] = datetime.now().strftime('%Y/%m/%d')

            self._db._data['users'][idx] = user

            with open(self._db._path, 'w') as f:
                json.dump(self._db._data, f)

        print(f'Unfollowed {deleted_users}/{max_users} users')

    def _scroll_down(self, num_pages):
        last_height = self._web.execute_script('return document.body.scrollHeight')

        posts = []

        for i in range(num_pages):
            self._web.execute_script('window.scrollTo(0, document.body.scrollHeight)')
            sleep(self.sleep_time)

            _posts = self._web.find_elements_by_xpath('//a[@href]')

            _posts = [p.get_attribute('href') for p in _posts]
            _posts = filter(lambda x: '/p/' in x, _posts)

            posts += list(_posts)

            new_height = self._web.execute_script('return document.body.scrollHeight')

            if new_height == last_height:
                break

            last_height = new_height

        return posts


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(required=True, dest='cmd')

    parser_config = subparsers.add_parser('config', help='configure the bot', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser_follow = subparsers.add_parser('follow', help='follow users', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser_unfollow = subparsers.add_parser('unfollow', help='unfollow users', formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    # CONFIG parser
    optional_config = parser_config._action_groups.pop()
    required_config = parser_config.add_argument_group('required arguments')

    # Required arguments for config
    required_config.add_argument('-u', '--user', required=True, default=argparse.SUPPRESS, metavar='USERNAME', help='set the account username')
    required_config.add_argument('-p', '--pass', required=True, default=argparse.SUPPRESS, metavar='PASSWORD', help='set the account password')

    # Optional arguments for config
    optional_config.add_argument('-t', '--tags', default='./data/tags', metavar='TAGS_FILE', help='set the tags file')
    optional_config.add_argument('-c', '--comments', default='./data/comments', metavar='COMMENTS_FILE', help='set the comments file')
    optional_config.add_argument('-r', '--prob_comment', default=0.1, metavar='PROB_COMMENT', help='set the probability of commenting a liked post')
    optional_config.add_argument('-i', '--interval', default=15, metavar='FOLLOW_UNFOLLOW_INTERVAL', help='set the time interval between follow/unfollow actions in days')
    optional_config.add_argument('-s', '--sleep', default=3, metavar='SLEEP_TIME', help='set the sleep time between bot actions in seconds')
    optional_config.add_argument('-d', '--database', default='./data/.instabot_db', metavar='DATABASE_FILE', help='set the database file')

    parser_config._action_groups.append(optional_config)

    # FOLLOW parser
    optional_follow = parser_follow._action_groups.pop()
    required_follow = parser_follow.add_argument_group('required arguments')

    # Required arguments for follow
    required_follow.add_argument('-n', '--num_users', required=True, default=argparse.SUPPRESS, metavar='NUM_USERS', help='set the number of users to follow')

    # Optional arguments for follow
    optional_follow.add_argument('-r', '--prob_comment', default=None, metavar='PROB_COMMENT', help='set the probability of commenting a liked post')
    optional_follow.add_argument('-i', '--interval', default=None, metavar='FOLLOW_UNFOLLOW_INTERVAL', help='set the time interval between follow/unfollow actions in days')
    optional_follow.add_argument('-s', '--sleep', default=None, metavar='SLEEP_TIME', help='set the sleep time between bot actions in seconds')

    parser_follow._action_groups.append(optional_follow)

    # UNFOLLOW parser
    optional_unfollow = parser_unfollow._action_groups.pop()
    required_unfollow = parser_unfollow.add_argument_group('required arguments')

    # Required arguments for unfollow
    required_unfollow.add_argument('-m', '--max_users', required=True, default=argparse.SUPPRESS, metavar='MAX_USERS', help='set the maximum number of users to unfollow')

    # Optional arguments for unfollow
    optional_unfollow.add_argument('-i', '--interval', default=None, metavar='FOLLOW_UNFOLLOW_INTERVAL', help='set the time interval between follow/unfollow actions in days')
    optional_unfollow.add_argument('-s', '--sleep', default=None, metavar='SLEEP_TIME', help='set the sleep time between bot actions in seconds')

    parser_unfollow._action_groups.append(optional_unfollow)

    args = parser.parse_args()

    if args.cmd == 'config':
        with open('./data/.instabot_config', 'w') as f:
            config = vars(args)
            config.pop('cmd')
            json.dump(config, f)
    elif args.cmd == 'follow':
        bot = InstaBot(sleep_time=args.sleep)
    else:
        pass




# bot = InstaBot(sleep_time=3)

# tags = ['alps', 'skimo', 'skitour', 'mountain', 'snow']
# comments = ['This is great!', 'So cool', 'Amazing!']

# bot.login(
#     username=os.environ['INSTA_USER'],
#     password=os.environ['INSTA_PASS'],
#     tags=tags,
#     comments=comments,
#     database='/home/marc/Desktop/instabot.db'
# )


# # bot.follow(num_users=3, comment_prob=0.1, days_to_wait=15)
# bot.unfollow(max_users=10, days_to_wait=0)
