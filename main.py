import streamlit as st
from supabase import create_client, Client
from typing import List, Tuple
import psycopg2
from dotenv import load_dotenv
import os
import pandas as pd
import altair as alt

# Load environment variables from .env
load_dotenv()

# Fetch variables from the environment
USER = os.getenv("user")
PASSWORD = os.getenv("password")
HOST = os.getenv("host")
PORT = os.getenv("port")
DBNAME = os.getenv("dbname")


# Initialize Supabase client using a direct connection string
def init_supabase_client(user, password, host, port, dbname) -> psycopg2.extensions.connection:
    """Initializes and returns a psycopg2 connection object."""
    try:
        conn = psycopg2.connect(
            user=user,
            password=password,
            host=host,
            port=port,
            dbname=dbname
        )
        print("Successfully connected to the database!")
        return conn
    except Exception as e:
        st.error(f"Failed to connect to the database: {e}.  Please ensure your database server is running and accessible.  Check your host, port, and socket configuration.")
        return None  # Return None in case of connection failure


# Accessibility Categories and Options (as defined previously)
CATEGORIES = {
    "Visual Accessibility": [
        "Subtitles & Closed Captions",
        "Colorblind Modes",
        "UI Customization",
        "Brightness & Contrast Adjustment",
        "Motion Blur Reduction",
        "Field of View (FOV) Adjustment",
        "Screen Shake Reduction",
    ],
    "Audio Accessibility": [
        "Volume Controls",
        "Visual Audio Cues",
        "Mono Audio",
    ],
    "Motor Accessibility": [
        "Controller Remapping",
        "Sensitivity Adjustment",
        "Button Hold/Toggle Options",
        "Aim Assist",
        "Motor Difficulty Settings",
        "Input Lag Reduction",
    ],
    "Cognitive Accessibility": [
        "Cognitive Difficulty Settings",
        "Clear UI Design",
        "Tutorials & Guidance",
        "Objective Markers & Navigation",
        "Narrative Clarity",
        "Reduced Time Limits",
    ],
    "General Accessibility Features": [
        "Accessibility Menu",
        "Presets",
        "Customization Saving",
        "Accessibility Information",
    ],
    "Localization": [
        "Text Language Options",
        "Audio Language Options",
        "Subtitle Language Options",
        "UI Language Options"
    ]
}

# Weights for Categories
WEIGHTS = {
    "Visual Accessibility": 0.25,
    "Audio Accessibility": 0.15,
    "Motor Accessibility": 0.25,
    "Cognitive Accessibility": 0.20,
    "General Accessibility Features": 0.10,
    "Localization": 0.05,
}

def calculate_score(selections: dict) -> Tuple[float, dict]:
    """Calculates the accessibility score based on user selections and returns category scores."""
    total_score = 0
    category_scores = {}
    for category, options in CATEGORIES.items():
        category_score = 0
        for option in options:
            if selections.get(option, False) == "Basic":
                category_score += 1
            elif selections.get(option, False) == "Customizable":
                category_score += 2
            elif selections.get(option, False) == "Extensive":
                category_score += 3
        weighted_score = WEIGHTS[category] * category_score
        total_score += weighted_score
        category_scores[category] = round(weighted_score, 2)
    return round(total_score, 2), category_scores

def insert_data_supabase(conn: psycopg2.extensions.connection, game_name: str, game_description: str, selections: dict, score: float, other_languages: List[str]) -> bool:
    """Inserts the game data into the Supabase tables using a direct connection."""
    try:
        cursor = conn.cursor()

        # 2. Insert into 'games' table
        cursor.execute("INSERT INTO games (name, description) VALUES (%s, %s) RETURNING id;", (game_name, game_description))
        game_id = cursor.fetchone()[0]

        # 3. Insert into 'submissions' table
        cursor.execute("INSERT INTO submissions (game_id, score, status) VALUES (%s, %s, %s) RETURNING id;", (game_id, score, 'pending'))
        submission_id = cursor.fetchone()[0]

        # 4. Insert into 'submission_features' table
        for option, level in selections.items():
            if level != "None":
                cursor.execute("SELECT id FROM accessibility_features WHERE name = %s;", (option,))
                feature_id = cursor.fetchone()[0]
                cursor.execute("INSERT INTO submission_features (submission_id, accessibility_feature_id, implementation_level) VALUES (%s, %s, %s);", (submission_id, feature_id, level))

        # 5. Insert into 'game_languages' table
        for lang_name in other_languages:
            if lang_name:
                cursor.execute("SELECT id FROM languages WHERE name = %s;", (lang_name,))
                language_id = cursor.fetchone()[0]
                cursor.execute("INSERT INTO game_languages (game_id, language_id) VALUES (%s, %s);", (game_id, language_id))

        # Commit the transaction
        conn.commit()
        cursor.close()
        return True

    except Exception as e:
        st.error(f"An error occurred: {e}")
        return False

def main():
    """Main function to run the Streamlit app."""
    st.title("Game Accessibility Submission Form")

    # Initialize database connection
    conn = init_supabase_client(USER, PASSWORD, HOST, PORT, DBNAME)
    if not conn:
        st.error("Failed to connect to the database. Please check your connection details and try again.")
        return  # Stop if the connection fails

    form_submitted = False

    if not form_submitted:
        # Game Name and Description Input
        game_name = st.text_input("Enter the Name of the Game:", "")
        game_description = st.text_area("Enter a brief description of the game:", "")

        # Accessibility Feature Selection
        selections = {}
        for category, options in CATEGORIES.items():
            st.subheader(category)
            for option in options:
                selections[option] = st.selectbox(
                    option,
                    ["None", "Basic", "Customizable", "Extensive"],
                    index=0,  # Default to "None"
                    key=f"{category}_{option}" # Unique key for each selectbox
                )

        # Fetch languages from the database
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM languages;")
            languages_data = cursor.fetchall()
            languages_list = [lang[0] for lang in languages_data]
            cursor.close()
        except Exception as e:
            st.error(f"Error fetching languages: {e}.  Please ensure your database server is running and accessible.  Check your host, port, and socket configuration.")
            languages_list = []

        # Language Selection (for Localization)
        other_languages = st.multiselect("Select the languages supported by the game:", languages_list)

        # Submit Button
        if st.button("Submit for Review", key="submit_button"):
            if not game_name:
                st.error("Please enter the game name.")
            elif not game_description:
                st.error("Please enter the game description")
            else:
                # Calculate the score
                score, category_scores = calculate_score(selections)
                # Insert data into Supabase
                if insert_data_supabase(conn, game_name, game_description, selections, score, other_languages):
                    st.success(f"Data submitted successfully! Your submission is pending review. Your Accessibility Score: {score}")
                    st.session_state['form_submitted'] = True
                    st.session_state['score'] = score
                    st.session_state['category_scores'] = category_scores
                else:
                    st.error("Failed to submit data. Please check the console for errors.")

    if 'form_submitted' in st.session_state and st.session_state['form_submitted']:
        st.subheader("Accessibility Score Breakdown")
        st.write(f"Your overall accessibility score is: **{st.session_state['score']}**")
        st.write("Here's a breakdown of your score by category:")

        category_data = []
        for category, score in st.session_state['category_scores'].items():
            category_data.append({'Category': category, 'Score': score})

        df = pd.DataFrame(category_data)

        # Create the bar chart using Altair
        chart = alt.Chart(df).mark_bar().encode(
            x='Category:N',
            y='Score:Q',
            tooltip=['Category', 'Score']
        ).properties(
            title='Accessibility Score by Category'
        )
        st.altair_chart(chart, use_container_width=True)

        st.write("\n**Explanation of Calculations:**")
        st.write("The overall accessibility score is calculated by considering the presence and level of implementation of various accessibility features across different categories.")
        st.write("For each selected accessibility feature, a score is assigned based on its implementation level:")
        st.markdown("- **None:** 0 points")
        st.markdown("- **Basic:** 1 point")
        st.markdown("- **Customizable:** 2 points")
        st.markdown("- **Extensive:** 3 points")
        st.write("These individual scores for each feature within a category are then summed up.")
        st.write("Finally, the score for each category is multiplied by a predefined weight to calculate the overall accessibility score.")
        st.write("The weights for each category are as follows:")
        for cat, weight in WEIGHTS.items():
            st.markdown(f"- **{cat}:** {weight}")

    if conn:
        conn.close()

if __name__ == "__main__":
    main()