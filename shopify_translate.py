import requests
from time import sleep
import openai

# Set your OpenAI API key here
openai.api_key = ''

# Configurable Area (place app token and shop username name below shop name isn't your domain name)
SHOPIFY_ACCESS_TOKEN = ''
SHOPIFY_SHOP_NAME = ''
LANGUAGE_TARGET = 'Swedish'


# Shopify GraphQL API URL
SHOPIFY_GRAPHQL_URL = f"https://{
    SHOPIFY_SHOP_NAME}.myshopify.com/admin/api/2023-04/graphql.json"


def shopify_graphql_query(query, variables=None):
    """Performs a Shopify GraphQL query with optional variables."""
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN
    }
    loaded = False
    for i in range(5):
        try:
            response = requests.post(
                SHOPIFY_GRAPHQL_URL,
                json={'query': query, 'variables': variables},
                headers=headers
            )
            loaded = True
            break
        except:
            print("Failed to connect to Shopify, retrying...")
    if not loaded:
        return None
    if response.status_code == 200:
        return response.json()
    else:
        print(f"GraphQL query failed with status code {response.status_code}")
        print(response.text)
        return None


def get_paginated_shopify_products(after_cursor=None):
    """Fetches paginated product titles and IDs from Shopify using GraphQL."""
    query = """
    query getProducts($after: String) {
      products(first: 200, after: $after, query: "status:active") {
        edges {
          node {
            id
            title
          }
          cursor
        }
        pageInfo {
          hasNextPage
        }
      }
    }
    """

    variables = {"after": after_cursor} if after_cursor else {}
    result = shopify_graphql_query(query, variables)

    if result and 'data' in result:
        products_data = result['data']['products']
        products = products_data['edges']
        has_next_page = products_data['pageInfo']['hasNextPage']
        last_cursor = products[-1]['cursor'] if products else None
        return products, has_next_page, last_cursor
    else:
        print("Failed to fetch products.")
        return [], False, None


def update_product_title(product_id, new_title):
    """Updates the product title and removes the default variant using Shopify GraphQL API."""

    # Step 1: Update the product title
    mutation = """
    mutation updateProductTitle($id: ID!, $title: String!) {
      productUpdate(input: {id: $id, title: $title}) {
        product {
          id
          title
          variants(first: 10) {
            edges {
              node {
                id
                title
              }
            }
          }
        }
        userErrors {
          field
          message
        }
      }
    }
    """
    variables = {
        "id": product_id,  # Shopify Product ID
        "title": new_title  # New title you want to set
    }

    response = shopify_graphql_query(mutation, variables)

    if 'errors' in response or response['data']['productUpdate']['userErrors']:
        print(f"Failed to update product title: {response}")
        return

    updated_title = response['data']['productUpdate']['product']['title']
    print(f"Product title successfully updated to: {updated_title}")


def translate_product_title(title):
    """Translates the product title to target language using OpenAI API or returns the original title if already in target language."""
    prompt = f"""
    Translate the following text to {LANGUAGE_TARGET}. If the text is already in {LANGUAGE_TARGET} or you cannot translate it for any reason, return it as is without enclosing quotes:

    "{title}"
    """

    client = openai.OpenAI(api_key=openai.api_key)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that translates text accurately and returns only the translation or the original text as instructed."},
            {"role": "user", "content": f"Translate the following text to {LANGUAGE_TARGET}. If the text is already in {LANGUAGE_TARGET} or you cannot translate it for any reason, return it as is without enclosing quotes:\n\"Ultrapods Pro True Wireless Earbuds with Display Transparent Design\""},
            {"role": "assistant",
                "content": "Ultrapods Pro True Wireless Earbuds med Display Transparent Design"},
            {"role": "user", "content": prompt}
        ]
    )

    translated_title = response.choices[0].message.content.strip()
    if translated_title.startswith('"'):
        translated_title = translated_title[1:]
    if translated_title.endswith('"'):
        translated_title = translated_title[:-1]

    return translated_title


if __name__ == "__main__":
    # Initialize cursor to None to start from the beginning
    after_cursor = None
    has_next_page = True

    # Loop through all pages of products
    while has_next_page:
        # Step 1: Get a paginated set of Shopify products
        loaded = False
        for i in range(6):
            try:
                products, has_next_page, after_cursor = get_paginated_shopify_products(
                    after_cursor)
                loaded = True
                break
            except Exception as e:
                print("Failed to connect to Shopify, retrying...")
                print(str(e))
        if not loaded:
            break

        print("Products returned: {}".format(len(products)))
        # Step 2: Translate and update product titles
        for product in products:
            product_id = product['node']['id']
            print(product_id)
            english_title = product['node']['title']
            print("Original Title: {}".format(english_title))
            translated = False
            for i in range(6):
                try:
                    other_lang_title = translate_product_title(english_title)
                    translated = True
                    break
                except Exception as e:
                    print("Failed to translate, retrying...")
                    print(str(e))
            if not translated:
                print("Failed to translate, skipping...")
                continue
            print("{} Title: {}".format(LANGUAGE_TARGET, other_lang_title))
            if english_title.strip().lower() == other_lang_title.strip().lower():
                print("Titles are the same, skipping...")
                continue
            updated = False
            for i in range(6):
                try:
                    update_product_title(product_id, other_lang_title)
                    updated = True
                    break
                except Exception as e:
                    print("Failed to update, retrying...")
                    print(str(e))

            sleep(0.1)  # Sleep to avoid hitting rate limits
