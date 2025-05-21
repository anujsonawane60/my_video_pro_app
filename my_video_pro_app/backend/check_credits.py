import os
from dotenv import load_dotenv
from voice_changer import VoiceChanger

# Load environment variables
load_dotenv()

def main():
    """Check available Eleven Labs credits"""
    try:
        # Initialize the voice changer
        print("Initializing VoiceChanger...")
        voice_changer = VoiceChanger()
        
        # Check user credits
        print("Checking Eleven Labs API credits...")
        subscription_data = voice_changer.check_user_credits()
        
        if subscription_data:
            character_limit = subscription_data.get('character_limit', 0)
            characters_used = subscription_data.get('character_count', 0)
            available_chars = character_limit - characters_used
            
            print(f"\nElevenLabs API Key: {voice_changer.api_key[:5]}...{voice_changer.api_key[-5:] if voice_changer.api_key else ''}")
            print(f"Available characters: {available_chars}")
            
            # Print subscription tier information if available
            tier = subscription_data.get('tier', 'Unknown')
            print(f"Subscription tier: {tier}")
            
            # Show next character reset date if available
            if 'next_character_count_reset_unix' in subscription_data:
                from datetime import datetime
                reset_time = datetime.fromtimestamp(subscription_data['next_character_count_reset_unix'])
                print(f"Next reset: {reset_time}")
                
            # Print quota information if available
            if 'character_limit' in subscription_data:
                print(f"Character limit: {character_limit}")
                print(f"Usage: {characters_used}/{character_limit} ({(characters_used / character_limit * 100 if character_limit else 0):.1f}%)")
        else:
            print("Failed to retrieve subscription data. Please check your API key.")
            
    except ValueError as e:
        print(f"Error: {e}")
        if "ELEVENLABS_API_KEY environment variable is not set" in str(e):
            print("\nPlease set your Eleven Labs API key in the .env file:")
            print("1. Create or edit a file named '.env' in the backend directory")
            print("2. Add this line: ELEVENLABS_API_KEY=your_actual_api_key_here")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    main() 