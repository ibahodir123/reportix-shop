# Dev-образ фронтенда (Vite dev server с HMR).
# Для прод-сборки статики добавим отдельный multi-stage позже.
FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]
