# main.py

from pipeline import RecommendationPipeline

if __name__ == "__main__":
    pipeline = RecommendationPipeline()
    
    query = "Я немного подавлен."
    bounds = {"lat_min": 55.70, "lat_max": 55.80, "lon_min": 37.50, "lon_max": 37.70}
    
    recs = pipeline.recommend(query, bounds)
    print(recs)