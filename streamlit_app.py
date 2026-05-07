import streamlit as st
import numpy as np
import pandas as pd
import warnings

# Suppress warnings
warnings.simplefilter(action='ignore', category=UserWarning)
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.simplefilter(action='ignore', category=DeprecationWarning)

# Function to check login credentials
def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["username"] == "shivam" and st.session_state["password"] == "shivam@5555":
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password.
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.button("Login", on_click=password_entered)
        return False
    elif not st.session_state["password_correct"]:
        # Password not correct, show input + error.
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.button("Login", on_click=password_entered)
        st.error("😕 User not known or password incorrect")
        return False
    else:
        # Password correct.
        return True

# Main application code (your existing functions go here)
def rate_purchase(row, max_prices):
    max_price = max_prices[row['ZZ0012']]
    if row['ZZ_PROD_MRP'] >= 0.9 * max_price:
        return 'A++'
    elif row['ZZ_PROD_MRP'] >= 0.8 * max_price:
        return 'A+'
    elif 0.75 * max_price <= row['ZZ_PROD_MRP'] < 0.8 * max_price:
        return 'A'
    elif 0.65 * max_price <= row['ZZ_PROD_MRP'] < 0.75 * max_price:
        return 'B'
    else:
        return 'C'

def get_order_sequence(user_id, crm, max_prices):
    user_orders = crm[crm['ZZSOLDTO'] == user_id].sort_values(by='ZZPURCHASE_DATE', ascending=True)
    user_category_sequence = user_orders['ZZ0012'].tolist()
    user_model_sequence = user_orders['ZZPROD_DESC'].tolist()
    purchase_date_sequence = user_orders['ZZPURCHASE_DATE'].dt.strftime('%Y-%m-%d').tolist()
    purchase_rating_sequence = user_orders['Purchase Rating'].tolist()
    price_diff_sequence = (user_orders['ZZ_PROD_MRP'] / user_orders['ZZ0012'].map(max_prices)).tolist()
    
    return user_category_sequence, user_model_sequence, purchase_date_sequence, purchase_rating_sequence, price_diff_sequence

def recommend_model(row, ifb_models_master):
    category = row['Recommend_New']
    budget_range = row['Budget Rating']
    
    if category not in ifb_models_master:
        return None, None
    
    category_df = ifb_models_master[category]
    
    # Define the order of ratings
    ratings_order = ['A++', 'A+', 'A', 'B', 'C']
    
    # Find the index of the current budget range
    try:
        current_index = ratings_order.index(budget_range)
    except ValueError:
        return None, None
    
    # Iterate through the ratings from the current budget range upwards
    for i in range(current_index, -1, -1):
        filtered_df = category_df[category_df['Rated'] == ratings_order[i]]
        
        if not filtered_df.empty:
            break
    
    # If no models found in higher ratings, check lower ratings
    if filtered_df.empty:
        for i in range(current_index + 1, len(ratings_order)):
            filtered_df = category_df[category_df['Rated'] == ratings_order[i]]
            
            if not filtered_df.empty:
                break
    
    if filtered_df.empty:
        return None, None
    
    # Sort by price, then by capacity (if exists), then by the number of non-null attributes
    if 'Capacity' in filtered_df.columns:
        filtered_df = filtered_df.sort_values(by=['Price', 'Capacity'], ascending=[True, False])
    else:
        filtered_df = filtered_df.sort_values(by='Price', ascending=True)
    
    # Count the number of non-null attributes for each model
    attribute_columns = [col for col in filtered_df.columns if col not in ['Product', 'Product_Code', 'Price', 'Rated']]
    filtered_df['Attribute_Count'] = filtered_df[attribute_columns].notnull().sum(axis=1)
    
    # Sort by attribute count
    filtered_df = filtered_df.sort_values(by='Attribute_Count', ascending=False)
    
    # Select the top model and its code
    recommended_model = filtered_df.iloc[0]['Product']
    recommended_model_code = filtered_df.iloc[0]['Product_Code']
    
    return recommended_model, recommended_model_code

# Streamlit Application
def main():
    st.title("Product Recommendation Engine")

    if check_password():
        # File upload for CRM data
        crm_file = st.file_uploader("Upload CRM Data (Excel)", type=["xlsx"])
        # File upload for Product Master List
        product_file = st.file_uploader("Upload Product Master List (Excel)", type=["xlsx"])

        if crm_file and product_file:
            try:
                # Read the uploaded files
                crm = pd.read_excel(crm_file, parse_dates=['ZZPURCHASE_DATE'])
                ifb_models_master = pd.read_excel(product_file, sheet_name=None)

                # Process CRM data
                crm['Phone Number'] = crm['ZZTEL_NUMBER'].fillna('').astype(str) + ', ' + crm['ZZALT_NUMBER'].fillna('').astype(str)
                crm['Phone Number'] = crm['Phone Number'].str.strip(', ')

                # Calculate the highest priced model within each product category
                max_prices = crm.groupby('ZZ0012')['ZZ_PROD_MRP'].max().to_dict()

                # Rate each purchase
                crm['Purchase Rating'] = crm.apply(lambda row: rate_purchase(row, max_prices), axis=1)

                # Calculate the overall budget rating for each customer
                crm['Budget Rating'] = crm.groupby('ZZSOLDTO')['Purchase Rating'].transform(lambda x: x.mode()[0])

                # Extract order sequences for all unique users
                all_user_ids = crm['ZZSOLDTO'].unique()
                sequence_list = []

                for user_id in all_user_ids:
                    user_category_sequence, user_model_sequence, purchase_date_sequence, purchase_rating_sequence, price_diff_sequence = get_order_sequence(user_id, crm, max_prices)
                    if user_category_sequence and user_model_sequence:
                        user_data = crm[crm['ZZSOLDTO'] == user_id].iloc[0]
                        sequence_row = [user_id, user_data['ZZNAME_ORG1'], user_data['Phone Number'], user_category_sequence, user_model_sequence, purchase_date_sequence, purchase_rating_sequence, price_diff_sequence, user_data['Budget Rating']]
                        sequence_list.append(sequence_row)

                sequence_df_columns = ['ZZSOLDTO', 'ZZNAME_ORG1', 'Phone Number', 'Order Sequence', 'Model Sequence', 'Purchase Date Sequence', 'Purchase Rating Sequence', 'Price Difference Sequence', 'Budget Rating']
                unique_sequences_df = pd.DataFrame(sequence_list, columns=sequence_df_columns)

                # Function to calculate standard budget rating
                def calculate_std_budget_rating(price_diff_sequence):
                    avg_price_diff = np.mean(price_diff_sequence)
                    if avg_price_diff >= 0.9:
                        return 'A++'
                    elif avg_price_diff >= 0.8:
                        return 'A+'
                    elif 0.75 <= avg_price_diff < 0.8:
                        return 'A'
                    elif 0.65 <= avg_price_diff < 0.75:
                        return 'B'
                    else:
                        return 'C'

                # Adding the Std_Budget_Rating column
                unique_sequences_df['Std_Budget_Rating'] = unique_sequences_df['Price Difference Sequence'].apply(calculate_std_budget_rating)

                # Remove duplicates based on 'Order Sequence' column
                unique_sequences_df = unique_sequences_df.drop_duplicates(subset=['Order Sequence'])

                # Determine the current season
                current_date = pd.to_datetime('today')
                def get_current_season():
                    month = current_date.month
                    if 3 <= month <= 5:
                        return 'Summer'
                    elif 6 <= month <= 9:
                        return 'Rainy'
                    elif 10 <= month <= 11:
                        return 'Autumn'
                    else:
                        return 'Winter'

                current_season = get_current_season()

                # Function to find similar customers and get recommendations
                def find_similar_customers_and_recommendations(customer_id, user_categories):
                    def sequence_similarity(seq1, seq2):
                        return sum(1 for a, b in zip(seq1, seq2) if a == b) / min(len(seq1), len(seq2))
                    
                    similar_customers = []
                    for other_customer_id, group in unique_sequences_df.groupby('ZZSOLDTO'):
                        if other_customer_id == customer_id:
                            continue
                        other_categories = group['Order Sequence'].tolist()[0]
                        similarity = sequence_similarity(user_categories, other_categories)
                        similar_customers.append((other_customer_id, similarity))
                    
                    similar_customers = sorted(similar_customers, key=lambda x: x[1], reverse=True)[:7]
                    
                    recommended_categories = []
                    for other_customer_id, _ in similar_customers:
                        other_orders = unique_sequences_df[unique_sequences_df['ZZSOLDTO'] == other_customer_id]
                        other_categories = other_orders['Order Sequence'].tolist()[0]
                        for category in reversed(other_categories):
                            if category not in user_categories:
                                recommended_categories.append(category)
                                break
                    
                    return recommended_categories

                # Combined function to get both new recommendation and possible recommendations
                def get_recommendations(row):
                    customer_id = row['ZZSOLDTO']
                    user_categories = row['Order Sequence']
                    
                    recommended_categories = find_similar_customers_and_recommendations(customer_id, user_categories)
                    
                    # Adjust recommendations based on the current season
                    if 'CD' in recommended_categories and current_season == 'Rainy':
                        recommended_categories.remove('CD')
                        recommended_categories.insert(0, 'CD')
                    if 'AC' in recommended_categories and current_season in ['Rainy', 'Autumn', 'Winter']:
                        recommended_categories.remove('AC')
                        recommended_categories.append('AC')
                        
                    new_recommendation = recommended_categories[0] if recommended_categories else None
                    possible_recommendations = recommended_categories
                    
                    return pd.Series([new_recommendation, possible_recommendations])

                # Apply the combined function to create the 'Recommend_New' and 'Possible_Recommendations' columns
                unique_sequences_df[['Recommend_New', 'Possible_Recommendations']] = unique_sequences_df.apply(get_recommendations, axis=1)

                # Apply the recommendation function to get 'Recommended_Model' and 'Recommended_Model_Code'
                unique_sequences_df['Recommended_Model'], unique_sequences_df['Recommended_Model_Code'] = zip(*unique_sequences_df.apply(recommend_model, args=(ifb_models_master,), axis=1))

                # Rename columns as per the new arrangement
                column_rename_map = {
                    'ZZSOLDTO': 'Customer ID',
                    'ZZNAME_ORG1': 'Customer Name',
                    'Order Sequence': 'Customer Category Purchase Sequence',
                    'Model Sequence': 'Customer Model Purchase Sequence',
                    'Std_Budget_Rating': 'Budget Range',
                    'Recommend_New': 'New Recommendation',
                    'Recommended_Model': 'Recommended Model',
                     'Recommended_Model_Code': 'Model Code'
                }

                unique_sequences_df = unique_sequences_df.rename(columns=column_rename_map)

                # Arrange columns in the specified order
                final_columns = ['Customer ID', 'Customer Name', 'Phone Number', 'Customer Category Purchase Sequence',
                                 'Customer Model Purchase Sequence', 'Purchase Date Sequence', 'Budget Range', 'New Recommendation',
                                 'Recommended Model', 'Model Code']

                final_output_df = unique_sequences_df[final_columns]

                # Display the final output
                st.write(final_output_df)

            except Exception as e:
                st.error(f"An error occurred while processing the files: {str(e)}")
        else:
            st.warning("Please upload both CRM data and Product Master List files.")

if __name__ == "__main__":
    main()