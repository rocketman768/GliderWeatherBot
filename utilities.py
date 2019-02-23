#!/usr/bin/env python

import random
import string

# Return a random string of lowercase letters of the given length
def randomString(length):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))
