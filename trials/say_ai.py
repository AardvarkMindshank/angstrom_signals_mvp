"""How the voice sounds out "MarketNavi.ai" spelt different ways (phonemes only)."""
from kokoro_onnx.tokenizer import Tokenizer

tok = Tokenizer()
for text in ["Market Navi dot ay eye.", "Market Navi dot A I.", "Market Navi dot A eye.", "Market Navi dot A.I.",
             "Market Navi dot AI.", "Market Navi dot eh eye.", "Market Navi dot A-I.", "Market Navi dot hay eye.",
             "Market Navi dot Ay, eye.", "Market Navi dot A, I."]:
    print(f"{text:30s} {tok.phonemize(text, 'en-gb')}")
