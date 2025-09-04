from flask import Flask, request, jsonify
from flask_cors import CORS
import httpx
from dotenv import load_dotenv
import pickle
import ast
import os
import asyncio
import numpy as np

load_dotenv()

OMDB_API_KEY = os.getenv('OMDB_API_KEY')
app = Flask(__name__)
CORS(app)


with open('data/movies.pkl', 'rb') as f:
    movies = pickle.load(f)

with open('data/movies_similarity.pkl', 'rb') as f:
    movies_similarity = pickle.load(f)

with open('data/books_data.pkl', 'rb') as f:
    books_data = pickle.load(f)

with open('data/books_similarity.pkl', 'rb') as f:
    books_similarity = pickle.load(f)

with open('data/pivote_table.pkl', 'rb') as f:
    pt = pickle.load(f)

with open('data/popular_books_data.pkl', 'rb') as f:
    popular_books_data = pickle.load(f)

with open('data/recommend_books_data.pkl', 'rb') as f:
    recommend_books_data = pickle.load(f)



async def recommend_movies(movie, count):
    recommended_movies = []

    try:
        index_tpl = movies[movies['title'].apply(lambda x: x.lower()) == movie.lower()].index
        if index_tpl.empty:
            index_tpl = movies[movies['genres'].apply(lambda x: isinstance(x, (list, set, tuple)) and movie in x)].index
    except Exception as e:
        print(e)

    if not index_tpl.empty:
        index = index_tpl[0]
        similarity_scores = list(enumerate(movies_similarity[index]))
        similar_movies = sorted(similarity_scores, reverse=True, key=lambda x: x[1])[:count + 1]

        async with httpx.AsyncClient() as client:
            for x in similar_movies:
                current_movie = movies.iloc[x[0]].copy()
                current_movie = current_movie.apply(lambda s: ast.literal_eval(s) if isinstance(s, str) and s.startswith('[') and s.endswith(']') else s)
                current_movie["title"] = current_movie["title"].capitalize()

                try:
                    url = f"http://www.omdbapi.com/?t={current_movie['title']}&apikey={OMDB_API_KEY}"
                    response = await client.get(url, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    current_movie["poster_url"] = data.get("Poster", None)
                except Exception as e:
                    print("error", e)
                    current_movie["poster_url"] = None

                recommended_movies.append(current_movie.to_dict())

    return recommended_movies


def recommend_books(book, count): 
    recommended_books = []
    books_array = pt.index.str.replace(' ', '').str.lower()
    book_idx = np.where(books_array == book.replace(' ', '').lower())  # In pt (pivote table) the index itself is the 'Book-Title', so to get its numarical index, we use np.where(pt.index == 'Book-Title')[0][0]
    if len(book_idx[0]) > 0:
        book_idx = book_idx[0][0]
        similarity_scores = list(enumerate(books_similarity[book_idx]))
        similar_books = sorted(similarity_scores, reverse=True, key=lambda x: x[1])[:count + 1]
        
        for x in similar_books:
            curr_series = recommend_books_data[recommend_books_data['Book-Title'] == pt.index[x[0]]]
            curr_dict = {}
            curr_dict['isbn'] = list(curr_series['ISBN'])[0]
            curr_dict['bookTitle'] = list(curr_series['Book-Title'])[0]
            curr_dict['bookAuthor'] = list(curr_series['Book-Author'])[0]
            curr_dict['publisher'] = list(curr_series['Publisher'])[0]
            curr_dict['yearOfPublication'] = list(curr_series['Year-Of-Publication'])[0]
            curr_dict['imageUrl'] = list(curr_series['Image-URL-L'])[0]
            recommended_books.append(curr_dict)
        
    return recommended_books

def get_popular_books(count):
    popular_books = []
    for i in range(count):
            curr_dict = {}
            curr_series = popular_books_data.iloc[i]
            curr_dict['isbn'] = curr_series['ISBN']
            curr_dict['bookTitle'] = curr_series['Book-Title']
            curr_dict['bookAuthor'] = curr_series['Book-Author']
            curr_dict['publisher'] = curr_series['Publisher']
            curr_dict['yearOfPublication'] = curr_series['Year-Of-Publication']
            curr_dict['imageUrl'] = curr_series['Image-URL-L']
            popular_books.append(curr_dict)

    return popular_books



@app.route("/recommend_movies")
def recommend_movies_route():
    movie = request.args.get('m')
    count = request.args.get('c')

    if count is None:
        count = 5
    
    count = int(count)

    if count > 15:
        count = 15

    if count < 1:
        count = 1

    if movie is None:
        return jsonify({"error": "No move specified!"}), 404

    try:
        recommended_movies = asyncio.run(recommend_movies(movie, count))
        if not recommended_movies:
            return jsonify({"error": "Movie not found"}), 404
        return jsonify({"recommended_movies": recommended_movies}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@app.route("/recommend_books")
def recommend_books_route():
    book = request.args.get('b')
    count = request.args.get('c')

    if book is None:
        return jsonify({"error:" "No book specified!"}), 404
    
    if count is None:
        count = 5
    
    count = int(count)

    if count > 15:
        count = 15

    if count < 1:
        count = 1


    
    try:
        recommended_books = recommend_books(book, count)
        if not recommended_books:
            return jsonify({"error": "Book is not so famous, no recommendations"}), 404
        return jsonify({"recommended_books": recommended_books}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@app.route("/popular_books")
def get_popular_books_route():
    count = request.args.get('c')

    if count is None:
        count = 5

    count = int(count)

    if count > 20:
        count = 20
    if count < 1:
        count = 1
    
    try:
        popular_books = get_popular_books(count)

        if not popular_books:
            return jsonify({"error": "No popular books"}), 404
        
        return jsonify({"popular_books": popular_books})
    except Exception as e:
        return jsonify({"error": str(e)}), 404


if __name__ == "__main__":
    app.run(debug=True)