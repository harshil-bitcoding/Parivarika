import jwt
import time

LANGUAGE_CHOICES = [
        ("guj", "Gujarati"),
    ]

_tokenKey = "FJrIfWHGHgl%#&#4844hiuh#%$#FJQTd756jsa%hK%^*skdj"
_algorithm = "HS256"

def encodedToken(data) : 
    return jwt.encode(data, _tokenKey, algorithm=_algorithm)

def decodedToken(encoded_data) : 
    return jwt.decode(encoded_data, _tokenKey, algorithm=_algorithm)

def getCurrentTimeInMilliseconds():
  current_time = time.time()
  return int(current_time * 1000)