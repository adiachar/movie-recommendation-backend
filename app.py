from flask import Flask, request, jsonify
from flask_cors import CORS
import httpx
from dotenv import load_dotenv
import pickle
import ast
import os
import asyncio
import requests

load_dotenv()

OMDB_API_KEY = os.getenv("OMDB_API_KEY")
app = Flask(__name__)
CORS(app)

MOVIES_FILE_ID = os.getenv("moviesPkl")
SIM_FILE_ID = os.getenv("moviesSimilarityPkl-")

def download_pickle_from_drive(file_id, filename):
    if not os.path.exists(filename):
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        r = requests.get(url)
        with open(filename, "wb") as f:
            f.write(r.content)

download_pickle_from_drive(MOVIES_FILE_ID, "movies.pkl")
download_pickle_from_drive(SIM_FILE_ID, "moviesSimilarity.pkl")

with open("movies.pkl", "rb") as f:
    movies = pickle.load(f)

with open("moviesSimilarity.pkl", "rb") as f:
    similarity = pickle.load(f)

async def recommend(movie, count):
    recommended_movies = []

    try: 
        index_tpl = movies[movies['title'] == movie.lower()].index
        if index_tpl.empty:
            index_tpl = movies[movies['genres'].apply(lambda x: isinstance(x, (list, set, tuple)) and movie in x)].index

    except Exception as e:
        print(e) 

    if not index_tpl.empty:
        index = index_tpl[0]
        similarity_scores = list(enumerate(similarity[index]))
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

@app.route("/recommend", methods=["POST"])
def recommend_movies():
    data = request.json
    movie = data.get("movie")
    count = data.get("count", 5)
    try:
        recommended_movies = asyncio.run(recommend(movie, count))
        if not recommended_movies:
            return jsonify({"error": "Movie not found"}), 404
        return jsonify({"recommended_movies": recommended_movies})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)