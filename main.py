import streamlit as st
from supabase import create_client, Client
from typing import List, Tuple
import psycopg2
from dotenv import load_dotenv
import os
import pandas as pd
import altair as alt
import matplotlib.pyplot as plt

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

# New Weights for Categories (Equal Weighting, out of 20 points)
NUM_CATEGORIES = len(CATEGORIES)
EQUAL_WEIGHT = 20 / NUM_CATEGORIES
NEW_WEIGHTS = {category: EQUAL_WEIGHT for category in CATEGORIES}

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
        weighted_score = NEW_WEIGHTS[category] * (category_score / 3 / len(CATEGORIES[category]) if len(CATEGORIES[category]) > 0 else 0) # Normalize by max points per category
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

def handle_submit(game_name, selections, conn, other_languages):
    """Handles the form submission logic."""
    if not game_name:
        st.error("Please enter the game name.")
        return

    # Calculate the score
    score, category_scores = calculate_score(selections)

    # Insert data into Supabase
    if insert_data_supabase(conn, game_name, "", selections, score, other_languages):  # Pass empty string for description
        st.success(f"🎉 Data submitted successfully! Your submission is pending review. Your Accessibility Score: **{score:.2f}/20** 🎉")
        st.session_state['form_submitted'] = True
        st.session_state['score'] = score
        st.session_state['category_scores'] = category_scores
        st.rerun()
    else:
        st.error("Failed to submit data. Please check the console for errors.")


def main():
    """Main function to run the Streamlit app."""
    st.markdown("<h1 style='text-align: center;'>Game Accessibility Submission Form 🎮</h1>", unsafe_allow_html=True)

    # 🎮 Welcome to the Game Accessibility Submission Form! 🕹️
    #
    # This form is designed to help you evaluate and submit information about
    # the accessibility features present in your game. By providing details about
    # various accessibility options, you contribute to making games more inclusive
    # for everyone.
    #
    # 📊 How the Score is Calculated (Out of 20 Points):
    # The overall accessibility score is now out of a total of 20 points.
    # Each of the following categories is weighted equally, contributing approximately
    # 3.33 points each to the total score:
    # - Visual Accessibility
    # - Audio Accessibility
    # - Motor Accessibility
    # - Cognitive Accessibility
    # - General Accessibility Features
    # - Localization
    #
    # 📝 How Points are Awarded:
    # For each selected accessibility feature, a score is awarded based on its
    # implementation level:
    # - None: 0 points
    # - Basic: 1 point
    # - Customizable: 2 points
    # - Extensive: 3 points
    #
    # The score for each category is calculated by summing the points for the
    # selected features within it. This sum is then normalized and weighted to
    # contribute equally to the total score out of 20 points.

    # Initialize database connection
    conn = init_supabase_client(USER, PASSWORD, HOST, PORT, DBNAME)
    if not conn:
        st.error("Failed to connect to the database. Please check your connection details and try again.")
        return  # Stop if the connection fails

    if 'form_submitted' not in st.session_state:
        st.session_state['form_submitted'] = False

    if not st.session_state['form_submitted']:
        st.subheader("Game Information 📝")
        # Game Name and Description Input
        game_name = st.text_input("Enter the Name of the Game:", placeholder="e.g., Awesome Adventure")
        # Removed game_description input

        st.subheader("Accessibility Features ⚙️")
        st.write("**How Points Work:** Select the implementation level for each feature:")
        st.markdown("- None: 0 points")
        st.markdown("- Basic: 1 point")
        st.markdown("- Customizable: 2 points")
        st.markdown("- Extensive: 3 points")
        st.write("The total accessibility score will be out of **20 points**.")

        selections = {}
        for category, options in CATEGORIES.items():
            st.subheader(f"➡️ {category}")
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
        st.subheader("Localization 🌍")
        other_languages = st.multiselect("Select the languages supported by the game:", languages_list)

    if not st.session_state['form_submitted']:
        if st.button("Submit for Review 🚀", key="submit_button") and not st.session_state['form_submitted']:
            handle_submit(game_name, selections, conn, other_languages)

    if st.session_state['form_submitted']:
        st.subheader("Accessibility Score Breakdown 📊")
        st.write(f"Your overall accessibility score is: **{st.session_state['score']:.2f}/20**")
        st.write("Here's a breakdown of your score by category:")

        category_data = []
        for category, score in st.session_state['category_scores'].items():
            category_data.append({'Category': category, 'Score': score})

        df = pd.DataFrame(category_data)

        if not df.empty:
            # Create the bar chart using Altair
            chart = alt.Chart(df).mark_bar().encode(
                x=alt.X('Category:N', sort=None, axis=alt.Axis(title='Category')), # Add axis title
                y=alt.Y('Score:Q', axis=alt.Axis(title='Score')), # Add axis title
                tooltip=['Category', 'Score']
            ).properties(
                title='Accessibility Score by Category (Out of 20)'
            ).interactive() # Make the chart interactive
            st.altair_chart(chart, use_container_width=True)

            # Additional Data Statistics
            st.subheader("More Insights 📈")
            st.write("Here's a view of the percentage of features selected for each category:")

            category_feature_counts = {}
            for category, options in CATEGORIES.items():
                category_feature_counts[category] = len(options)

            category_percentages = []
            for category, score in st.session_state['category_scores'].items():
                max_score_per_category = 3 * category_feature_counts.get(category, 0)
                if max_score_per_category > 0:
                    percentage = (score / NEW_WEIGHTS[category]) * (NEW_WEIGHTS[category] / max_score_per_category) * 100
                    category_percentages.append({'Category': category, 'Percentage of Max': percentage})
                else:
                    category_percentages.append({'Category': category, 'Percentage of Max': 0})

            df_percentages = pd.DataFrame(category_percentages)

            # Bar Chart using Altair for Percentages
            percentage_chart = alt.Chart(df_percentages).mark_bar().encode(
                x=alt.X('Category:N', sort=None, axis=alt.Axis(title='Category')),
                y=alt.Y('Percentage of Max:Q', title='Percentage of Max Features (%)'),
                tooltip=['Category', alt.Tooltip('Percentage of Max', format='.1f')]
            ).properties(
                title='Percentage of Maximum Possible Features Implemented per Category'
            ).interactive()
            st.altair_chart(percentage_chart, use_container_width=True)

            # Pie Chart using Altair for Percentages
            pie_chart = alt.Chart(df_percentages).mark_arc(outerRadius=120).encode(
                theta=alt.Theta(field="Percentage of Max", type="quantitative"),
                color=alt.Color(field="Category", type="nominal"),
                order=alt.Order("Percentage of Max", sort="descending"),
                tooltip=["Category", alt.Tooltip("Percentage of Max", format=".1f")]
            ).properties(
                title='Percentage of Maximum Possible Features per Category (Pie Chart)'
            ).interactive()
            st.altair_chart(pie_chart, use_container_width=True)

        else:
            st.warning("No category scores to display.")

        st.write("\n**Explanation of Calculations 💡:**")
        st.write("The overall accessibility score is now out of 20 points, with each of the 6 main categories contributing equally.")
        st.write("For each selected accessibility feature, a score is awarded based on its implementation level:")
        st.markdown("- **None:** 0 points")
        st.markdown("- **Basic:** 1 point")
        st.markdown("- **Customizable:** 2 points")
        st.markdown("- **Extensive:** 3 points")
        st.write("The score for each category is calculated by summing the points for the selected features within it. This sum is then normalized and weighted to contribute to the total score of 20 points.")
        st.write("**Category Weights (Equal):**")
        for cat in CATEGORIES.keys():
            st.markdown(f"- **{cat}:** {EQUAL_WEIGHT:.2f} points")

        # Button to submit another form
        if st.button("Submit Another Form 📝"):
            st.session_state['form_submitted'] = False
            st.rerun()

    if conn:
        conn.close()

if __name__ == "__main__":
    main()