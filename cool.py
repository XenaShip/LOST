from telegraph import Telegraph

telegraph = Telegraph()
resp = telegraph.create_account(
    short_name='arendatoriy',        # любое короткое имя
    author_name='Arendatoriy',       # подпись автора (необязательно)
    author_url='https://t.me/arendatoriy_find_bot'
)
print(resp)                          # тут будет 'access_token'
print("TOKEN =", resp["access_token"])