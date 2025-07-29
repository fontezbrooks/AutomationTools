#!/usr/bin/env python3
"""
PDF Recipe to Obsidian Markdown Converter
Processes Tasty Shreds recipe PDFs and converts them to Obsidian-compatible markdown files.
"""

import os
import re
import glob
from typing import List, Dict
import logging

try:
    import fitz  # PyMuPDF - Primary PDF library

    PDF_LIBRARY = "PyMuPDF"
except ImportError:
    try:
        import PyPDF2

        PDF_LIBRARY = "PyPDF2"
        fitz = None
    except ImportError:
        print("Error: Neither PyMuPDF nor PyPDF2 could be imported.")
        print("Please install one of them:")
        print("  pip install PyMuPDF")
        print("  pip install PyPDF2")
        exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RecipeExtractor:
    """Extracts and processes recipe data from PDF files."""

    def __init__(self):
        self.ingredient_tags = {
            # Proteins
            "chicken": ["chicken", "chicken breast", "chicken tender"],
            "turkey": [
                "turkey",
                "turkey bacon",
                "turkey sausage",
                "turkey chorizo",
                "turkey pepperoni",
            ],
            "beef": ["beef", "ground beef", "steak"],
            "pork": ["pork", "bacon", "ham"],
            "fish": ["fish", "salmon", "tuna", "cod"],
            "egg": ["egg", "egg white", "eggs"],
            # Meal types
            "breakfast": [
                "breakfast",
                "bagel",
                "waffle",
                "pancake",
                "burrito",
                "scramble",
            ],
            "lunch": ["lunch", "sandwich", "wrap", "salad"],
            "dinner": ["dinner", "pasta", "rice", "stir fry"],
            "snack": ["snack", "bar", "bite", "ball"],
            # Food types
            "pizza": ["pizza", "flatbread", "pita"],
            "pasta": ["pasta", "noodle", "spaghetti", "penne"],
            "sandwich": ["sandwich", "sub", "hoagie"],
            "burrito": ["burrito", "wrap", "tortilla"],
            "bagel": ["bagel"],
            "waffle": ["waffle"],
            "pancake": ["pancake"],
            "salad": ["salad", "bowl"],
            # Cooking methods
            "airfryer": ["air fryer", "airfryer"],
            "baked": ["baked", "oven", "broil"],
            "grilled": ["grilled", "grill"],
            # Dietary
            "lowcarb": ["low carb", "keto", "carb balance"],
            "highprotein": ["protein", "high protein"],
            "fatfree": ["fat free", "fat-free"],
        }

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF using available library."""
        if fitz is not None:
            # Use PyMuPDF (more reliable)
            try:
                doc = fitz.open(pdf_path)
                text = ""
                for page in doc:
                    text += page.get_text()
                doc.close()
                return text
            except Exception as e:
                logger.error(f"Error extracting text with PyMuPDF from {pdf_path}: {e}")

        # Fallback to or use PyPDF2
        try:
            with open(pdf_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text()
                return text
        except Exception as e2:
            logger.error(f"Error extracting text with PyPDF2 from {pdf_path}: {e2}")
            return ""

    def parse_recipe_data(self, text: str) -> Dict[str, any]:
        """Parse recipe data from extracted text."""
        recipe_data = {
            "title": "",
            "calories": "",
            "protein": "",
            "ingredients": [],
            "directions": [],
            "pro_tips": [],
        }

        # Clean up text
        text = re.sub(r"\s+", " ", text.strip())

        # Extract title - usually the largest text or first meaningful line
        title_patterns = [
            r"([A-Z][^.!?\n]*(?:breakfast|lunch|dinner|pizza|sandwich|burrito|bagel|waffle|pancake|salad|bowl|plate|wrap)[^.!?\n]*)",
            r"([A-Z][a-z\s]+(?:chicken|turkey|beef|pork|fish)[^.!?\n]*)",
            r"^([A-Z][^.!?\n]{10,50})",
        ]

        for pattern in title_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                potential_title = match.group(1).strip()
                # Clean up title
                potential_title = re.sub(r"^[0-9]+\.?\s*", "", potential_title)
                if len(potential_title) > 5 and not potential_title.lower().startswith(
                    ("throw", "add", "cook", "place")
                ):
                    recipe_data["title"] = potential_title
                    break

        # If no title found, try to extract from common recipe names
        if not recipe_data["title"]:
            common_names = re.findall(
                r"([A-Za-z\s.]+(?:burrito|pizza|sandwich|bagel|waffle|pancake|salad|bowl|plate))",
                text,
                re.IGNORECASE,
            )
            if common_names:
                recipe_data["title"] = common_names[0].strip()

        # Extract calories and protein
        calorie_match = re.search(r"(\d+)\s*calories", text, re.IGNORECASE)
        if calorie_match:
            recipe_data["calories"] = calorie_match.group(1)

        protein_match = re.search(r"(\d+)\s*grams?\s*of\s*protein", text, re.IGNORECASE)
        if protein_match:
            recipe_data["protein"] = protein_match.group(1)

        # Extract ingredients
        ingredients_section = re.search(
            r"Ingredients\s*(.*?)(?:Directions|$)", text, re.IGNORECASE | re.DOTALL
        )
        if ingredients_section:
            ingredients_text = ingredients_section.group(1)
            # Split by lines and clean up
            for line in ingredients_text.split("\n"):
                line = line.strip()
                if line and not line.lower().startswith(("directions", "pro tip")):
                    # Remove bullet points and numbers
                    line = re.sub(r"^[•\-\*\d]+\.?\s*", "", line)
                    if line:
                        recipe_data["ingredients"].append(line)

        # Extract directions
        directions_section = re.search(
            r"Directions\s*(.*?)(?:PRO TIP|$)", text, re.IGNORECASE | re.DOTALL
        )
        if directions_section:
            directions_text = directions_section.group(1)
            # Split by numbered steps
            steps = re.findall(r"(\d+\..*?)(?=\d+\.|$)", directions_text, re.DOTALL)
            for step in steps:
                step = step.strip()
                if step:
                    # Clean up step
                    step = re.sub(r"^\d+\.?\s*", "", step)
                    recipe_data["directions"].append(step.strip())

        # Extract pro tips
        pro_tips_section = re.search(
            r"PRO TIP[S]?\s*(.*?)$", text, re.IGNORECASE | re.DOTALL
        )
        if pro_tips_section:
            tips_text = pro_tips_section.group(1)
            # Split by numbered tips
            tips = re.findall(r"(\d+\..*?)(?=\d+\.|$)", tips_text, re.DOTALL)
            for tip in tips:
                tip = tip.strip()
                if tip:
                    # Clean up tip
                    tip = re.sub(r"^\d+\.?\s*", "", tip)
                    recipe_data["pro_tips"].append(tip.strip())

        return recipe_data

    def generate_tags(self, recipe_data: Dict[str, any]) -> List[str]:
        """Generate tags based on recipe content."""
        tags = set()

        # Combine all text to analyze
        all_text = " ".join(
            [
                recipe_data["title"],
                " ".join(recipe_data["ingredients"]),
                " ".join(recipe_data["directions"]),
            ]
        ).lower()

        # Check for ingredient-based tags
        for tag, keywords in self.ingredient_tags.items():
            for keyword in keywords:
                if keyword.lower() in all_text:
                    tags.add(tag)
                    break

        # Add nutrition-based tags
        if recipe_data["calories"]:
            calories = int(recipe_data["calories"])
            if calories < 300:
                tags.add("lowcalorie")
            elif calories > 500:
                tags.add("highcalorie")

        if recipe_data["protein"]:
            protein = int(recipe_data["protein"])
            if protein > 40:
                tags.add("highprotein")

        # Ensure we have at least some tags
        if not tags:
            tags.add("recipe")

        return sorted(list(tags))

    def create_markdown(self, recipe_data: Dict[str, any]) -> str:
        """Create Obsidian-compatible markdown from recipe data."""
        tags = self.generate_tags(recipe_data)
        tag_string = " ".join([f"#{tag}" for tag in tags])

        markdown = f"# {recipe_data['title']}\n\n"
        markdown += f"{tag_string}\n\n"

        # Nutrition info
        if recipe_data["calories"] or recipe_data["protein"]:
            markdown += "## Nutrition Information\n\n"
            if recipe_data["calories"]:
                markdown += f"- **Calories:** {recipe_data['calories']}\n"
            if recipe_data["protein"]:
                markdown += f"- **Protein:** {recipe_data['protein']}g\n"
            markdown += "\n"

        # Ingredients
        if recipe_data["ingredients"]:
            markdown += "## Ingredients\n\n"
            for ingredient in recipe_data["ingredients"]:
                markdown += f"- {ingredient}\n"
            markdown += "\n"

        # Directions
        if recipe_data["directions"]:
            markdown += "## Directions\n\n"
            for i, direction in enumerate(recipe_data["directions"], 1):
                markdown += f"{i}. {direction}\n"
            markdown += "\n"

        # Pro Tips
        if recipe_data["pro_tips"]:
            markdown += "## Pro Tips\n\n"
            for tip in recipe_data["pro_tips"]:
                markdown += f"- {tip}\n"
            markdown += "\n"

        return markdown

    def sanitize_filename(self, title: str) -> str:
        """Sanitize title for use as filename."""
        # Remove or replace invalid characters
        sanitized = re.sub(r'[<>:"/\\|?*]', "", title)
        sanitized = re.sub(r"[^\w\s-]", "", sanitized)
        sanitized = re.sub(r"\s+", " ", sanitized).strip()
        sanitized = sanitized.replace(" ", "_")

        # Limit length
        if len(sanitized) > 50:
            sanitized = sanitized[:50].rstrip("_")

        return sanitized or "recipe"

    def process_pdf_file(self, pdf_path: str, output_dir: str) -> bool:
        """Process a single PDF file."""
        try:
            logger.info(f"Processing {os.path.basename(pdf_path)}")

            # Extract text
            text = self.extract_text_from_pdf(pdf_path)
            if not text:
                logger.warning(f"No text extracted from {pdf_path}")
                return False

            # Parse recipe data
            recipe_data = self.parse_recipe_data(text)
            if not recipe_data["title"]:
                # Use filename as fallback title
                filename = os.path.splitext(os.path.basename(pdf_path))[0]
                recipe_data["title"] = filename.replace(
                    "Tasty Shreds Jan-Feb-March_Part", "Recipe "
                )

            # Create markdown
            markdown = self.create_markdown(recipe_data)

            # Save to file
            filename = self.sanitize_filename(recipe_data["title"])
            output_path = os.path.join(output_dir, f"{filename}.md")

            # Handle duplicate filenames
            counter = 1
            original_output_path = output_path
            while os.path.exists(output_path):
                base_name = os.path.splitext(original_output_path)[0]
                output_path = f"{base_name}_{counter}.md"
                counter += 1

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown)

            logger.info(f"Created: {os.path.basename(output_path)}")
            return True

        except Exception as e:
            logger.error(f"Error processing {pdf_path}: {e}")
            return False

    def process_all_pdfs(self, directory: str = ".") -> None:
        """Process all matching PDF files in the directory."""
        # Find all matching PDF files
        pattern = os.path.join(directory, "Tasty Shreds Jan-Feb-March_Part*.pdf")
        pdf_files = glob.glob(pattern)

        if not pdf_files:
            logger.error(f"No PDF files found matching pattern: {pattern}")
            return

        # Sort files numerically
        pdf_files.sort(key=lambda x: int(re.search(r"Part(\d+)", x).group(1)))

        logger.info(f"Found {len(pdf_files)} PDF files to process")

        # Create output directory
        output_dir = os.path.join(directory, "obsidian_recipes")
        os.makedirs(output_dir, exist_ok=True)

        # Process each file
        successful = 0
        failed = 0

        for pdf_file in pdf_files:
            if self.process_pdf_file(pdf_file, output_dir):
                successful += 1
            else:
                failed += 1

        logger.info(f"Processing complete: {successful} successful, {failed} failed")
        logger.info(f"Markdown files saved to: {output_dir}")


def main():
    """Main function to run the converter."""
    print("Tasty Shreds PDF to Obsidian Markdown Converter")
    print("=" * 50)

    # Get current directory
    current_dir = os.getcwd()
    print(f"Working directory: {current_dir}")

    # Initialize extractor
    extractor = RecipeExtractor()

    # Process all PDFs
    extractor.process_all_pdfs(current_dir)

    print(
        "\nConversion complete! Check the 'obsidian_recipes' folder for your markdown files."
    )


if __name__ == "__main__":
    main()
