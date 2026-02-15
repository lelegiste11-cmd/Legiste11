"""
Card prediction logic for Joker's Telegram Bot - simplified for webhook deployment
"""

import re
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any
import time
import os
import json

logger = logging.getLogger(__name__)

# Configuration constants
VALID_CARD_COMBINATIONS = [
    "♠️♥️♦️", "♠️♥️♣️", "♠️♦️♣️", "♥️♦️♣️"
]

CARD_SYMBOLS = ["♠️", "♥️", "♦️", "♣️", "❤️"]  # Include both ♥️ and ❤️ variants

# PREDICTION_MESSAGE is now handled directly in make_prediction method

# Target channel ID for Baccarat Kouamé
TARGET_CHANNEL_ID = -1002682552255

# Target channel ID for predictions and updates
PREDICTION_CHANNEL_ID = -1002875505624

class CardPredictor:
    """Handles card prediction logic for webhook deployment"""

    def __init__(self):
        self.predictions = {}  # Store predictions for verification
        self.processed_messages = set()  # Avoid duplicate processing
        self.sent_predictions = {}  # Store sent prediction messages for editing
        self.temporary_messages = {}  # Store temporary messages waiting for final edit
        self.pending_edits = {}  # Store messages waiting for edit with indicators
        self.position_preference = 1  # Default position preference (1 = first card, 2 = second card)
        self.redirect_channels = {}  # Store redirection channels for different chats
        self.last_prediction_time = self._load_last_prediction_time()  # Load persisted timestamp
        self.prediction_cooldown = 30   # Cooldown period in seconds between predictions

    def _load_last_prediction_time(self) -> float:
        """Load last prediction timestamp from file"""
        try:
            if os.path.exists('.last_prediction_time'):
                with open('.last_prediction_time', 'r') as f:
                    timestamp = float(f.read().strip())
                    logger.info(f"⏰ PERSISTANCE - Dernière prédiction chargée: {time.time() - timestamp:.1f}s écoulées")
                    return timestamp
        except Exception as e:
            logger.warning(f"⚠️ Impossible de charger le timestamp: {e}")
        return 0

    def _save_last_prediction_time(self):
        """Save last prediction timestamp to file"""
        try:
            with open('.last_prediction_time', 'w') as f:
                f.write(str(self.last_prediction_time))
        except Exception as e:
            logger.warning(f"⚠️ Impossible de sauvegarder le timestamp: {e}")

    def reset_predictions(self):
        """Reset all prediction states - useful for recalibration"""
        self.predictions.clear()
        self.processed_messages.clear()
        self.sent_predictions.clear()
        self.temporary_messages.clear()
        self.pending_edits.clear()
        self.last_prediction_time = 0
        self._save_last_prediction_time()
        logger.info("🔄 Système de prédictions réinitialisé")

    def set_position_preference(self, position: int):
        """Set the position preference for card selection (1 or 2)"""
        if position in [1, 2]:
            self.position_preference = position
            logger.info(f"🎯 Position de carte mise à jour : {position}")
        else:
            logger.warning(f"⚠️ Position invalide : {position}. Utilisation de la position par défaut (1).")

    def set_redirect_channel(self, source_chat_id: int, target_chat_id: int):
        """Set redirection channel for predictions from a source chat"""
        self.redirect_channels[source_chat_id] = target_chat_id
        logger.info(f"📤 Redirection configurée : {source_chat_id} → {target_chat_id}")

    def get_redirect_channel(self, source_chat_id: int) -> int:
        """Get redirect channel for a source chat, fallback to PREDICTION_CHANNEL_ID"""
        return self.redirect_channels.get(source_chat_id, PREDICTION_CHANNEL_ID)

    def reset_all_predictions(self):
        """Reset all predictions and redirect channels"""
        self.predictions.clear()
        self.processed_messages.clear()
        self.sent_predictions.clear()
        self.temporary_messages.clear()
        self.pending_edits.clear()
        self.redirect_channels.clear()
        self.last_prediction_time = 0
        self._save_last_prediction_time()
        logger.info("🔄 Toutes les prédictions et redirections ont été supprimées")

    def extract_game_number(self, message: str) -> Optional[int]:
        """Extract game number from message like #n744 or #N744"""
        pattern = r'#[nN](\d+)'
        match = re.search(pattern, message)
        if match:
            return int(match.group(1))
        return None

    def extract_cards_from_parentheses(self, message: str) -> List[str]:
        """Extract cards from first and second parentheses"""
        # This method is deprecated, use extract_card_symbols_from_parentheses instead
        return []

    def has_pending_indicators(self, text: str) -> bool:
        """Check if message contains indicators suggesting it will be edited"""
        indicators = ['⏰', '▶', '🕐', '➡️']
        return any(indicator in text for indicator in indicators)

    def has_completion_indicators(self, text: str) -> bool:
        """Check if message contains completion indicators after edit - ✅ OR 🔰 indicates completion"""
        completion_indicators = ['✅', '🔰']
        has_indicator = any(indicator in text for indicator in completion_indicators)
        if has_indicator:
            indicator_found = next(ind for ind in completion_indicators if ind in text)
            logger.info(f"🔍 FINALISATION DÉTECTÉE - Indicateur {indicator_found} trouvé dans: {text[:100]}...")
        return has_indicator

    def should_wait_for_edit(self, text: str, message_id: int) -> bool:
        """Determine if we should wait for this message to be edited"""
        if self.has_pending_indicators(text):
            # Store this message as pending edit
            self.pending_edits[message_id] = {
                'original_text': text,
                'timestamp': datetime.now()
            }
            return True
        return False

    def extract_card_symbols_from_parentheses(self, text: str) -> List[List[str]]:
        """Extract unique card symbols from each parentheses section"""
        # Find all parentheses content
        pattern = r'\(([^)]+)\)'
        matches = re.findall(pattern, text)

        all_sections = []
        for match in matches:
            # Normalize ❤️ to ♥️ for consistency
            normalized_content = match.replace("❤️", "♥️")

            # Extract only unique card symbols (costumes) from this section
            unique_symbols = set()
            for symbol in ["♠️", "♥️", "♦️", "♣️"]:
                if symbol in normalized_content:
                    unique_symbols.add(symbol)

            all_sections.append(list(unique_symbols))

        return all_sections

    def has_three_different_cards(self, cards: List[str]) -> bool:
        """Check if there are exactly 3 different card symbols"""
        unique_cards = list(set(cards))
        logger.info(f"Checking cards: {cards}, unique: {unique_cards}, count: {len(unique_cards)}")
        return len(unique_cards) == 3

    def is_temporary_message(self, message: str) -> bool:
        """Check if message contains temporary progress emojis"""
        temporary_emojis = ['⏰', '▶', '🕐', '➡️']
        return any(emoji in message for emoji in temporary_emojis)

    def is_final_message(self, message: str) -> bool:
        """Check if message contains final completion emojis - NOW ONLY 🔰"""
        final_emojis = ['🔰']
        is_final = any(emoji in message for emoji in final_emojis)
        if is_final:
            logger.info(f"🔍 MESSAGE FINAL DÉTECTÉ - Emoji 🔰 trouvé dans: {message[:100]}...")
        return is_final

    def get_card_combination(self, cards: List[str]) -> Optional[str]:
        """Get the combination of 3 different cards"""
        unique_cards = list(set(cards))
        if len(unique_cards) == 3:
            combination = ''.join(sorted(unique_cards))
            logger.info(f"Card combination found: {combination} from cards: {unique_cards}")

            # Check if this combination matches any valid pattern
            for valid_combo in VALID_CARD_COMBINATIONS:
                if set(combination) == set(valid_combo):
                    logger.info(f"Valid combination matched: {valid_combo}")
                    return combination

            # Accept any 3 different cards as valid
            logger.info(f"Accepting 3 different cards as valid: {combination}")
            return combination
        return None

    def extract_costumes_from_second_parentheses(self, message: str) -> List[str]:
        """Extract only costumes from exactly 3 cards in the second parentheses"""
        # Find all parentheses content
        pattern = r'\(([^)]+)\)'
        matches = re.findall(pattern, message)

        if len(matches) < 2:
            return []

        second_parentheses = matches[1]  # Second parentheses (index 1)
        logger.info(f"Deuxième parenthèses contenu: {second_parentheses}")

        # Extract only costume symbols (♠️, ♥️, ♦️, ♣️, ❤️)
        costumes = []
        costume_symbols = ["♠️", "♥️", "♦️", "♣️", "❤️"]

        # Normalize ❤️ to ♥️ for consistency
        normalized_content = second_parentheses.replace("❤️", "♥️")

        # Find all costume symbols in order of appearance
        for char_pos in range(len(normalized_content) - 1):
            two_char_symbol = normalized_content[char_pos:char_pos + 2]
            if two_char_symbol in ["♠️", "♥️", "♦️", "♣️"]:
                costumes.append(two_char_symbol)

        logger.info(f"Costumes extraits de la deuxième parenthèse: {costumes}")
        return costumes

    def find_missing_color(self, message: str) -> Optional[Tuple[str, int]]:
        """
        NOUVELLE RÈGLE: Trouver la couleur manquante dans les 2 premiers groupes
        CONDITION: Chaque groupe doit contenir exactement 2 cartes
        Returns: (missing_color, prediction_offset) ou None

        Règles de distance:
        - ♣️ (trèfle) manque → +4
        - ♦️ (carreau) manque → +4
        - ♠️ (pique) manque → +2
        - ♥️ (cœur) manque → +2
        """
        # Normaliser ❤️ vers ♥️
        normalized_message = message.replace("❤️", "♥️")

        # Extraire les 2 premiers groupes de parenthèses
        pattern = r'\(([^)]+)\)'
        matches = re.findall(pattern, normalized_message)

        if len(matches) < 2:
            logger.info(f"🔮 COULEUR MANQUANTE - Moins de 2 groupes trouvés")
            return None

        first_group = matches[0]
        second_group = matches[1]

        logger.info(f"🔮 ANALYSE - Groupe 1: {first_group}")
        logger.info(f"🔮 ANALYSE - Groupe 2: {second_group}")

        # VÉRIFICATION OBLIGATOIRE: Compter TOUTES les cartes (occurrences) dans chaque groupe
        all_colors = ["♠️", "♥️", "♦️", "♣️"]

        # Compter le nombre TOTAL d'occurrences de couleurs dans le groupe 1
        group1_card_count = sum(first_group.count(color) for color in all_colors)
        # Compter le nombre TOTAL d'occurrences de couleurs dans le groupe 2
        group2_card_count = sum(second_group.count(color) for color in all_colors)

        logger.info(f"🔮 COMPTAGE - Groupe 1: {group1_card_count} cartes, Groupe 2: {group2_card_count} cartes")

        # VALIDATION: Chaque groupe doit avoir EXACTEMENT 2 cartes
        if group1_card_count != 2:
            logger.info(f"🔮 ❌ REJETÉ - Groupe 1 n'a pas exactement 2 cartes ({group1_card_count} trouvées)")
            return None

        if group2_card_count != 2:
            logger.info(f"🔮 ❌ REJETÉ - Groupe 2 n'a pas exactement 2 cartes ({group2_card_count} trouvées)")
            return None

        logger.info(f"🔮 ✅ VALIDATION - Chaque groupe a exactement 2 cartes")

        # Combiner les couleurs des 2 premiers groupes
        combined = first_group + second_group

        # Trouver les couleurs présentes
        all_colors_set = {"♠️", "♥️", "♦️", "♣️"}
        present_colors = set()

        for color in all_colors_set:
            if color in combined:
                present_colors.add(color)

        # Trouver la couleur manquante
        missing_colors = all_colors_set - present_colors

        if len(missing_colors) != 1:
            logger.info(f"🔮 COULEUR MANQUANTE - Pas exactement 1 couleur manquante: {missing_colors}")
            return None

        missing_color = missing_colors.pop()

        # Déterminer l'offset de prédiction selon la couleur manquante
        if missing_color in ["♣️", "♦️"]:
            prediction_offset = 4
        elif missing_color in ["♠️", "♥️"]:
            prediction_offset = 2
        else:
            return None

        logger.info(f"🔮 ✅ COULEUR MANQUANTE TROUVÉE: {missing_color} → Prédire à +{prediction_offset}")
        return (missing_color, prediction_offset)

    def can_make_prediction(self) -> bool:
        """Check if enough time has passed since last prediction (70 seconds cooldown)"""
        current_time = time.time()

        # Si aucune prédiction n'a été faite encore, autoriser
        if self.last_prediction_time == 0:
            logger.info(f"⏰ PREMIÈRE PRÉDICTION: Aucune prédiction précédente, autorisation accordée")
            return True

        time_since_last = current_time - self.last_prediction_time

        if time_since_last >= self.prediction_cooldown:
            logger.info(f"⏰ COOLDOWN OK: {time_since_last:.1f}s écoulées depuis dernière prédiction (≥{self.prediction_cooldown}s)")
            return True
        else:
            remaining = self.prediction_cooldown - time_since_last
            logger.info(f"⏰ COOLDOWN ACTIF: Encore {remaining:.1f}s à attendre avant prochaine prédiction")
            return False

    def should_predict(self, message: str) -> Tuple[bool, Optional[int], Optional[Tuple[str, int]]]:
        """
        NOUVELLE RÈGLE DE PRÉDICTION:
        1. Analyser SEULEMENT les messages avec #R
        2. Trouver la couleur manquante dans les 2 premiers groupes
        3. Prédire selon la couleur: ♣️/♦️ → +4, ♠️/♥️ → +2
        Returns: (should_predict, game_number, (predicted_costume, offset))
        """
        # Extract game number
        game_number = self.extract_game_number(message)
        if not game_number:
            return False, None, None

        logger.debug(f"🔮 PRÉDICTION - Analyse du jeu {game_number}")

        # ANALYSE EXCLUSIVE: SEULEMENT les messages avec #R
        if '#R' not in message:
            logger.info(f"🔮 EXCLUSION - Jeu {game_number}: Ne contient pas #R, pas de prédiction")
            return False, None, None

        logger.info(f"🔮 ✅ MESSAGE #R DÉTECTÉ - Jeu {game_number}: Analyse activée")

        # Exclure #X (match nul) même avec #R
        if '#X' in message:
            logger.info(f"🔮 EXCLUSION - Jeu {game_number}: Contient #X (match nul), pas de prédiction")
            return False, None, None

        # Check if this is a temporary message (should wait for final edit)
        if self.has_pending_indicators(message) and not self.has_completion_indicators(message):
            logger.info(f"🔮 Jeu {game_number}: Message temporaire (⏰▶🕐➡️), attente finalisation")
            self.temporary_messages[game_number] = message
            return False, None, None

        # Check if this is a final message (has completion indicators)
        if self.has_completion_indicators(message):
            logger.info(f"🔮 Jeu {game_number}: Message final détecté (✅ ou 🔰)")
            # Remove from temporary if it was there
            if game_number in self.temporary_messages:
                del self.temporary_messages[game_number]
                logger.info(f"🔮 Jeu {game_number}: Retiré des messages temporaires")

        # If the message still has waiting indicators, don't process
        elif self.has_pending_indicators(message):
            logger.info(f"🔮 Jeu {game_number}: Encore des indicateurs d'attente, pas de prédiction")
            return False, None, None

        # CHECK COOLDOWN BEFORE ANY PREDICTION
        if not self.can_make_prediction():
            logger.info(f"🔮 COOLDOWN - Jeu {game_number}: Attente cooldown de {self.prediction_cooldown}s, prédiction différée")
            return False, None, None

        # NOUVELLE RÈGLE: Trouver la couleur manquante
        missing_color_result = self.find_missing_color(message)
        if not missing_color_result:
            logger.info(f"🔮 AUCUNE PRÉDICTION - Jeu {game_number}: Impossible de déterminer la couleur manquante")
            return False, None, None

        predicted_costume, prediction_offset = missing_color_result
        target_game = game_number + prediction_offset

        # Skip if we already have a prediction for this target game
        if target_game in self.predictions and self.predictions[target_game].get('status') == 'pending':
            logger.info(f"🔮 Jeu {game_number}: Prédiction N{target_game} déjà existante, éviter doublon")
            return False, None, None

        # Prevent duplicate processing
        message_hash = hash(message)
        if message_hash not in self.processed_messages:
            self.processed_messages.add(message_hash)
            # Update last prediction timestamp and save
            self.last_prediction_time = time.time()
            self._save_last_prediction_time()
            logger.info(f"🔮 PREDICTION - Game {game_number}: GENERATING prediction for game {target_game} (+{prediction_offset}) with costume {predicted_costume}")
            logger.info(f"⏰ COOLDOWN - Next prediction possible in {self.prediction_cooldown}s")
            return True, game_number, (predicted_costume, prediction_offset)
        else:
            logger.info(f"🔮 PREDICTION - Game {game_number}: ⚠️ Already processed")
            return False, None, None

    def make_prediction(self, game_number: int, prediction_data: Tuple[str, int]) -> str:
        """
        Make a prediction with custom offset
        prediction_data: (predicted_costume, offset)
        """
        predicted_costume, offset = prediction_data
        target_game = game_number + offset

        # Simplified prediction message format
        prediction_text = f"🔵{target_game}🔵:{predicted_costume} statut :⏳"

        # Store the prediction for later verification
        self.predictions[target_game] = {
            'predicted_costume': predicted_costume,
            'status': 'pending',
            'predicted_from': game_number,
            'verification_count': 0,
            'message_text': prediction_text,
            'offset': offset
        }

        logger.info(f"Made prediction for game {target_game} (offset +{offset}) based on costume {predicted_costume}")
        return prediction_text

    def get_costume_text(self, costume_emoji: str) -> str:
        """Convert costume emoji to text representation"""
        costume_map = {
            "♠️": "pique",
            "♥️": "coeur",
            "♦️": "carreau",
            "♣️": "trèfle"
        }
        return costume_map.get(costume_emoji, "inconnu")

    def count_cards_in_winning_parentheses(self, message: str) -> int:
        """Count the number of card symbols in the parentheses that has the 🔰 symbol"""
        # Split message at 🔰 to find which section won
        if '🔰' not in message:
            return 0

        # Find the parentheses after 🔰
        checkmark_pos = message.find('🔰')
        remaining_text = message[checkmark_pos:]

        # Extract parentheses content after 🔰
        pattern = r'\(([^)]+)\)'
        match = re.search(pattern, remaining_text)

        if match:
            winning_content = match.group(1)
            # Normalize ❤️ to ♥️ for consistent counting
            normalized_content = winning_content.replace("❤️", "♥️")
            card_count = 0
            for symbol in ["♠️", "♥️", "♦️", "♣️"]:
                card_count += normalized_content.count(symbol)
            logger.info(f"Found 🔰 winning section: {winning_content}, card count: {card_count}")
            return card_count

        return 0

    def count_cards_in_first_parentheses(self, message: str) -> int:
        """Count the total number of card symbols in the first parentheses"""
        # Find first parentheses content
        pattern = r'\(([^)]+)\)'
        match = re.search(pattern, message)

        if match:
            first_content = match.group(1)
            # Normalize ❤️ to ♥️ for consistent counting
            normalized_content = first_content.replace("❤️", "♥️")
            card_count = 0
            for symbol in ["♠️", "♥️", "♦️", "♣️"]:
                card_count += normalized_content.count(symbol)
            logger.info(f"Found first parentheses: {first_content}, card count: {card_count}")
            return card_count

        return 0

    def verify_prediction(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Déléguer à la méthode commune de vérification
        """
        return self._verify_prediction_common(text, is_edited=False)


    def verify_prediction_from_edit(self, message: str) -> Optional[Dict]:
        """Verify if a prediction was correct from edited message (enhanced verification)"""
        return self._verify_prediction_common(message, is_edited=True)

    def check_costume_in_first_parentheses(self, message: str, predicted_costume: str) -> bool:
        """Vérifier si le costume prédit apparaît SEULEMENT dans le PREMIER parenthèses"""
        # Normaliser ❤️ vers ♥️ pour cohérence
        normalized_message = message.replace("❤️", "♥️")
        normalized_costume = predicted_costume.replace("❤️", "♥️")

        # Extraire SEULEMENT le contenu du PREMIER parenthèses
        pattern = r'\(([^)]+)\)'
        matches = re.findall(pattern, normalized_message)

        if not matches:
            logger.info(f"🔍 Aucun parenthèses trouvé dans le message")
            return False

        first_parentheses_content = matches[0]  # SEULEMENT le premier
        logger.info(f"🔍 VÉRIFICATION PREMIER PARENTHÈSES SEULEMENT: {first_parentheses_content}")

        costume_found = normalized_costume in first_parentheses_content
        logger.info(f"🔍 Recherche costume {normalized_costume} dans PREMIER parenthèses: {costume_found}")
        return costume_found

    def _verify_prediction_common(self, text: str, is_edited: bool = False) -> Optional[Dict]:
        """SYSTÈME DE VÉRIFICATION CORRIGÉ - Vérifie séquentiellement +0, +1, +2, +3 avec ARRÊT immédiat"""
        game_number = self.extract_game_number(text)
        if not game_number:
            return None

        logger.info(f"🔍 VÉRIFICATION - Jeu {game_number} (édité: {is_edited})")

        # SYSTÈME DE VÉRIFICATION: Sur messages édités OU normaux avec symbole succès (✅ ou 🔰)
        has_success_symbol = self.has_completion_indicators(text)
        if not has_success_symbol:
            logger.info(f"🔍 ⏸️ Pas de vérification - Aucun symbole de succès (✅ ou 🔰) trouvé")
            return None

        logger.info(f"🔍 📊 ÉTAT ACTUEL - Prédictions stockées: {list(self.predictions.keys())}")

        # Si aucune prédiction stockée, pas de vérification possible
        if not self.predictions:
            logger.info(f"🔍 ✅ VÉRIFICATION TERMINÉE - Aucune prédiction éligible")
            return None

        # VÉRIFICATION STRICTE: Pour chaque prédiction en attente, vérifier UNIQUEMENT son offset actuel
        for predicted_game in sorted(self.predictions.keys()):
            prediction = self.predictions[predicted_game]

            # Vérifier seulement les prédictions en attente
            if prediction.get('status') != 'pending':
                continue

            # Calculer l'offset actuel
            verification_offset = game_number - int(predicted_game) # Ensure predicted_game is int for subtraction

            # Vérifier SEULEMENT si l'offset est dans [0, 1, 2, 3]
            if verification_offset not in [0, 1, 2, 3]:
                continue

            predicted_costume = prediction.get('predicted_costume')
            if not predicted_costume:
                continue

            logger.info(f"🔍 🎯 TEST OFFSET +{verification_offset} - Prédiction {predicted_game} vs Jeu {game_number}")

            # Vérifier si le costume prédit est présent
            costume_found = self.check_costume_in_first_parentheses(text, predicted_costume)

            if costume_found:
                # ✅ SUCCÈS à cet offset - ARRÊT IMMÉDIAT
                status_symbol = f"✅{verification_offset}️⃣"
                original_message = prediction['message_text'] # Use stored message
                updated_message = original_message.replace('⏳', status_symbol) # Replace pending indicator

                prediction['status'] = 'correct'
                prediction['verification_count'] = verification_offset
                prediction['final_message'] = updated_message

                logger.info(f"🔍 ✅ SUCCÈS OFFSET +{verification_offset} - ARRÊT sur prédiction {predicted_game}")

                return {
                    'type': 'edit_message',
                    'predicted_game': predicted_game,
                    'new_message': updated_message,
                    'original_message': original_message
                }

            # ❌ ÉCHEC à cet offset
            if verification_offset == 3:
                # Dernier essai (offset +3) - Marquer ❌ et ARRÊT
                original_message = prediction['message_text'] # Use stored message
                updated_message = original_message.replace('⏳', '❌')

                prediction['status'] = 'failed'
                prediction['final_message'] = updated_message

                logger.info(f"🔍 ❌ Échec FINAL OFFSET +3 - ARRÊT sur prédiction {predicted_game}")

                return {
                    'type': 'edit_message',
                    'predicted_game': predicted_game,
                    'new_message': updated_message,
                    'original_message': original_message
                }
            else:
                # Offset 0, 1, ou 2 - Attendre le prochain offset
                logger.info(f"🔍 ⏭️ Échec OFFSET +{verification_offset} - Attente offset +{verification_offset+1}")
                # Ne rien faire, attendre le prochain message

        logger.info(f"🔍 ✅ VÉRIFICATION TERMINÉE - Aucune action requise")
        return None

# Global instance
card_predictor = CardPredictor()