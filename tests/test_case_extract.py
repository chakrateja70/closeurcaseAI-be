import asyncio

from src.services.case_ingestion import extract_text

x = asyncio.run(
    extract_text(
        case_text="This is a test case text.",
        urls=[
            "https://firebasestorage.googleapis.com/v0/b/quantumads-verify.firebasestorage.app/o/teja%2FWhatsApp%20Image%202026-09-17%20at%2011.10.20%20AM.jpeg?alt=media&token=4f74abe5-d7f8-4ad5-8ebb-94ad236131bd",
            "https://firebasestorage.googleapis.com/v0/b/quantumads-verify.firebasestorage.app/o/teja%2FWP%20No.35209%20of%202025%20Valluru%20Feroz%20Ahamad%20(1).pdf?alt=media&token=b50829ad-af10-490a-bffa-b0d932197ff3",
        ],
    )
)


print(x)
