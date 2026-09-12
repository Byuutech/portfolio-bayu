/* ===================================
   CUSTOM CURSOR
=================================== */

const cursor = document.querySelector(".cursor");
const cursorGlow = document.querySelector(".cursor-glow");

let mouseX = 0;
let mouseY = 0;

let glowX = 0;
let glowY = 0;

document.addEventListener("mousemove", (e) => {

    mouseX = e.clientX;
    mouseY = e.clientY;

    cursor.style.left = mouseX + "px";
    cursor.style.top = mouseY + "px";

});


/* ===================================
   SMOOTH CURSOR GLOW
=================================== */

function animateGlow() {

    glowX += (mouseX - glowX) * 0.08;
    glowY += (mouseY - glowY) * 0.08;

    cursorGlow.style.left = glowX + "px";
    cursorGlow.style.top = glowY + "px";

    requestAnimationFrame(animateGlow);
}

animateGlow();


/* ===================================
   CURSOR HOVER EFFECT
=================================== */

const interactiveElements = document.querySelectorAll(
    "a, button, .skill-card, .project-card"
);

interactiveElements.forEach((element) => {

    element.addEventListener("mouseenter", () => {

        cursor.style.width = "22px";
        cursor.style.height = "22px";

        cursor.style.mixBlendMode = "difference";

    });

    element.addEventListener("mouseleave", () => {

        cursor.style.width = "10px";
        cursor.style.height = "10px";

        cursor.style.mixBlendMode = "normal";

    });

});


/* ===================================
   3D TILT EFFECT
=================================== */

const tiltElements = document.querySelectorAll(".tilt");

tiltElements.forEach((element) => {

    element.addEventListener("mousemove", (e) => {

        const rect = element.getBoundingClientRect();

        const x =
            e.clientX - rect.left;

        const y =
            e.clientY - rect.top;

        const centerX =
            rect.width / 2;

        const centerY =
            rect.height / 2;

        const rotateX =
            ((y - centerY) / centerY) * -5;

        const rotateY =
            ((x - centerX) / centerX) * 5;

        element.style.transform =
            `perspective(1000px)
             rotateX(${rotateX}deg)
             rotateY(${rotateY}deg)
             translateY(-5px)`;

    });


    element.addEventListener("mouseleave", () => {

        element.style.transform =
            `perspective(1000px)
             rotateX(0deg)
             rotateY(0deg)
             translateY(0px)`;

    });

});


/* ===================================
   MAGNETIC BUTTON
=================================== */

const magneticElements =
    document.querySelectorAll(".magnetic");

magneticElements.forEach((element) => {

    element.addEventListener("mousemove", (e) => {

        const rect =
            element.getBoundingClientRect();

        const x =
            e.clientX - rect.left - rect.width / 2;

        const y =
            e.clientY - rect.top - rect.height / 2;

        element.style.transform =
            `translate(${x * 0.18}px, ${y * 0.18}px)`;

    });


    element.addEventListener("mouseleave", () => {

        element.style.transform =
            "translate(0, 0)";

    });

});


/* ===================================
   SCROLL REVEAL
=================================== */

const revealElements =
    document.querySelectorAll(
        ".section, .skill-card, .project-card"
    );

const revealObserver =
    new IntersectionObserver(
        (entries) => {

            entries.forEach((entry) => {

                if (entry.isIntersecting) {

                    entry.target.classList.add("visible");

                }

            });

        },
        {
            threshold: 0.12
        }
    );


revealElements.forEach((element) => {

    element.classList.add("reveal");

    revealObserver.observe(element);

});


/* ===================================
   DYNAMIC MOUSE BACKGROUND
=================================== */

document.addEventListener("mousemove", (e) => {

    const x =
        (e.clientX / window.innerWidth) * 100;

    const y =
        (e.clientY / window.innerHeight) * 100;

    document.body.style.setProperty(
        "--mouse-x",
        `${x}%`
    );

    document.body.style.setProperty(
        "--mouse-y",
        `${y}%`
    );

});