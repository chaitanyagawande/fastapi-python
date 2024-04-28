from exceptiongroup import catch
from exif import Image
import google.generativeai as genai
import PIL.Image
from json_utils import extract_json_object
import os
from dotenv import load_dotenv
import json

load_dotenv()

class GeminiAPI:

    def __init__(self, path) -> None:
        self.image_path = path
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

        self.generation_config = {
            "temperature": 0.2,
            "top_p": 0.95,
            "top_k": 0,
            "max_output_tokens": 8192,
        }

        self.safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
        ]

        self.system_instruction = """
            Act an expert in analysing image related to waste.
            you should analyze the image to identify the type of waste (e.g., plastic, organic, electronic) and estimate the level of waste present.
            based on image give a detail summary of waste.
            you should identify location as par latitude and longitude and give brief summary of surrounding location and how important it to be clean.
            you should also identify nearby landmarks relevant to waste disposal (e.g., recycling centers, waste facilities), assess the environmental impact, and estimate the number of people required for cleanup based on general government standards.
            Additionally, you should provide actionable cleaning suggestions tailored to the type of waste identified, complete with safety tips and presented in a step-by-step guide format. These suggestions are designed for individuals to perform immediately if needed
        """

        self.prompt = '''
        Anaylse Image & location
        location :  "position": {
                        "lat": 45.51999,
                        "lng": -122.68005}
        generate response like a Example below:
        example :
        Provide the response in JSON format with the following fields:
        {
        "Description": A brief summary of what input image is based on location and waste,
        "Type_of_waste": Choose option of type of waste answer from following option (eg. plastic, organic, paper,industrial, household, hazard,chemical,liquid, Mixed etc). If no waste is detected, set this to 'none',
        "location_summary": A very short string describing the location summary based on position & how waste is impacting the environment,
        "impact": A very short describtion of impact of waste on location & type & quantity of waste(less than 20 words),
        "impact_level": A string that rate impact of waste on environment based on surronding such as 'Harmful', 'Moderately Harmful','Less Harmful', 'Potentially Beneficial',
        "emergency": Identify Priority level like if is a 'cricital','High','Medium','Low','Routine' based on surronding, type of waste & level of waste,
        "reward": Give a reward score based on impact ,impact_level,emergency out of 100(eg 50),
        "Level_of_waste":  A string that rates the level of waste present such as 'low', 'mid', or 'high'. If no waste is detected, set this to 'none',
        "Nearby_landmarks": Find nearby landmarks based on location relevant to waste disposal (e.g., recycling centers, waste facilities) give response as list of landmarks with estimated distance like ['name':'','distance':'  in miles']. If not found set this to ['none'],
        "people_required": estimated the exact number of people required for cleanup waste based on general government standards,(eg. 3, 4 etc). If not needed set this to 0,
        "suggestion":  {
            "safety precautions": 3 precaution. if not needed set empty list.
            []
            "Steps": 5 steps.if not needed set empty list.
            []
            "Additional tips": 3 one line tips.if not needed set empty list.
            []
        }
        you should provide actionable cleaning suggestions tailored to the type of waste identified, complete with safety tips and presented in a step-by-step guide format.These suggestions are designed for individuals to perform immediately if needed
        }
        '''

    def generate_content(self):
        model = genai.GenerativeModel(
            model_name="gemini-1.5-pro-latest",
            generation_config=self.generation_config,
            system_instruction=self.system_instruction,
            safety_settings=self.safety_settings
        )

        input_img = PIL.Image.open(self.image_path)
        
        response = model.generate_content([self.prompt, input_img])
        cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned_text)

        image_coordinates = {}
        try:
            image_coordinates = self.image_coordinates(self.image_path)
        except Exception as e:
            print("Error in getting image coordinates", e)

        print(image_coordinates)

        return data

    def decimal_coords(self, coords, ref):
        decimal_degrees = coords[0] + coords[1] / 60 + coords[2] / 3600
        if ref == "S" or ref =='W' :
            decimal_degrees = -decimal_degrees
        return decimal_degrees

    def image_coordinates(self, image_path):

        with open(image_path, 'rb') as src:
            img = Image(src)
        if img.has_exif:
            try:
                img.gps_longitude
                print( img.gps_longitude)
                coords = (self.decimal_coords(img.gps_latitude,
                        img.gps_latitude_ref),
                        self.decimal_coords(img.gps_longitude,
                        img.gps_longitude_ref))
            except AttributeError:
                print ('No Coordinates')
        else:
            print ('The Image has no EXIF information')

        return({"imageTakenTime":img.datetime_original, "geolocation_lat":coords[0],"geolocation_lng":coords[1]})


