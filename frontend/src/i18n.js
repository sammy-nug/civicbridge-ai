// Chat-page text in each language. Hausa, Yoruba and Igbo were drafted by AI and have
// NOT been reviewed by a human; the UI says so whenever one of these languages is selected.
export const LANGUAGE_OPTIONS = [
  { code: "en", label: "English", reviewed: true },
  { code: "ha", label: "Hausa", reviewed: false },
  { code: "yo", label: "Yorùbá", reviewed: false },
  { code: "ig", label: "Igbo", reviewed: false },
];

export const CHAT_TEXT = {
  en: {
    placeholder: "Ask about voting, PVCs, election rules…",
    send: "Send",
    suggestions: [
      "How do I register to vote?",
      "How can I transfer my voter registration?",
      "What documents do I need for voter registration?",
      "How can I replace a lost PVC?",
      "How can I learn about election observation?",
    ],
  },
  ha: {
    placeholder: "Yi tambaya game da zaɓe, PVC, dokokin zaɓe…",
    send: "Aika",
    suggestions: [
      "Ta yaya zan yi rajistar zaɓe?",
      "Ta yaya zan canja wurin rajistar zaɓe ta?",
      "Wadanne takardu nake bukata don rajistar zaɓe?",
      "Ta yaya zan maye gurbin PVC da ta ɓace?",
      "Ta yaya zan koyi game da sa ido a zaɓe?",
    ],
  },
  yo: {
    placeholder: "Béèrè nípa ìdìbò, PVC, òfin ìdìbò…",
    send: "Fi ránṣẹ́",
    suggestions: [
      "Báwo ni mo ṣe lè forúkọ sílẹ̀ láti dìbò?",
      "Báwo ni mo ṣe lè gbé ìforúkọsílẹ̀ ìdìbò mi lọ sí ibòmíràn?",
      "Àwọn ìwé wo ni mo nílò fún ìforúkọsílẹ̀ ìdìbò?",
      "Báwo ni mo ṣe lè rí PVC mìíràn tí tèmi bá sọnù?",
      "Báwo ni mo ṣe lè kọ́ nípa ìṣàkíyèsí ìdìbò?",
    ],
  },
  ig: {
    placeholder: "Jụọ maka ntuli aka, PVC, iwu ntuli aka…",
    send: "Zipu",
    suggestions: [
      "Kedu ka m ga-esi deba aha m maka ntuli aka?",
      "Kedu ka m ga-esi bufee ndebanye aha ntuli aka m?",
      "Akwụkwọ ndị dị aṅaa ka m chọrọ maka ndebanye aha ntuli aka?",
      "Kedu ka m ga-esi nweta PVC ọhụrụ ma nke m furu efu?",
      "Kedu ka m ga-esi mụta banyere ikiri ntuli aka?",
    ],
  },
};
