// Plain module (no "use client") so the server layout can inline the script text.
export const THEME_KEY = "aiia-theme";

/** Runs before paint (inlined in <head>) so a saved light theme never flashes dark. */
export const THEME_BOOT_SCRIPT = `try{if(localStorage.getItem("${THEME_KEY}")==="light"){var d=document.documentElement;d.classList.remove("dark");d.classList.add("light");d.style.colorScheme="light"}}catch(e){}`;
