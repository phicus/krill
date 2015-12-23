# Author: Hemanth Sethuram
# Email: hemanthps@gmail.com
# Date: 16 Sep 2005
# Modifications: 
# 27 Jul 2006
#    1. Changed ALPHABETS set. This follows the keyboard layout and their shifted versions.
#    2. Added CONST_STRING
#    3. Added a new password generation function for GeneratePassword() and
#    deprecated the random number based password generation.
#    4. Passphrase is now Identifier + Master Password + CONST_STRING
# 12 Nov 2006
#    1. Added a new Password generation method using base64 encoding. Just use the string
#       representation of the hash and encode it as base64. This becomes the password with
#      alphanumeric characters.
#    2. Renamed the old password generation function to GeneratePasswordWithCharSet()

import sha, string

def get_pots_charset_password(charset, passString, passLength):
    """This function creates a SHA-1 hash from the passString. The 40 nibbles of
    this hash are used as indexes into the charset from where the characters are
    picked. This is again shuffled by repeating the above process on this subset.
    Finally the required number of characters are returned as the generated
    password"""
    assert passLength <= 40   # because we want to use sha-1 (160 bits)
    charlen = len(charset)
    c1 = []
    n = 0
    s = sha.sha(passString).hexdigest() # this gives a 40 nibble string (160 bits)
    for nibble in s:
        n = (n + string.atoi(nibble,16)) % charlen
        c1.append(charset[n])  # this will finally generate a 40 character list
        
    # Repeat the above loop to scramble this set again
    n = 0
    c2 = []
    for nibble in s:
        n = (n + string.atoi(nibble,16)) % 40   # for 40 nibbles
        c2.append(c1[n])
    
    # Now truncate this character list to the required length and return
    return "".join(c2[-passLength:])
